"""
数据加载器
加载 WorldQuant Operators 和 Fields
"""
import json
from pathlib import Path
from typing import List, Dict, Set
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
FIELDS_DIR = BASE_DIR / "data" / "wq_fields"
OPERATORS_FILE = BASE_DIR / "data" / "wq_operators" / "operators.json"


class DataLoader:
    """加载和管理 WQ 数据字段和操作符"""
    
    def __init__(self, enabled_datasets: List[str] = None):
        """
        Args:
            enabled_datasets: 启用的数据集列表，如 ['pv1', 'fundamental6']
                             如果为 None，加载所有数据集
        """
        self.enabled_datasets = enabled_datasets
        self._operators = None
        self._fields = None
        self._fields_by_dataset = None
    
    def load_operators(self) -> List[Dict]:
        """加载所有操作符"""
        if self._operators is not None:
            return self._operators
        
        if not OPERATORS_FILE.exists():
            raise FileNotFoundError(f"Operators file not found: {OPERATORS_FILE}")
        
        with open(OPERATORS_FILE, 'r', encoding='utf-8') as f:
            self._operators = json.load(f)
        
        logger.info(f"✅ Loaded {len(self._operators)} operators")
        return self._operators
    
    def load_fields(self) -> List[Dict]:
        """加载所有字段（根据 enabled_datasets 过滤）"""
        if self._fields is not None:
            return self._fields
        
        all_fields = []
        self._fields_by_dataset = {}
        
        for json_file in FIELDS_DIR.glob("*.json"):
            dataset_name = json_file.stem
            
            # 如果指定了 enabled_datasets，只加载这些数据集
            if self.enabled_datasets and dataset_name not in self.enabled_datasets:
                continue
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    fields = json.load(f)
                
                # 为每个字段添加 dataset 信息
                for field in fields:
                    field['dataset_name'] = dataset_name
                
                all_fields.extend(fields)
                self._fields_by_dataset[dataset_name] = fields
                
                logger.info(f"✅ Loaded {len(fields)} fields from {dataset_name}")
                
            except Exception as e:
                logger.error(f"❌ Failed to load {json_file.name}: {e}")
        
        self._fields = all_fields
        logger.info(f"✅ Total loaded: {len(all_fields)} fields from {len(self._fields_by_dataset)} datasets")
        return all_fields
    
    def get_operator_names(self) -> List[str]:
        """获取所有操作符名称"""
        operators = self.load_operators()
        return [op['name'] for op in operators]
    
    def get_operators_by_category(self) -> Dict[str, List[str]]:
        """按类别分组操作符"""
        operators = self.load_operators()
        grouped = {}
        
        for op in operators:
            category = op.get('category', 'Other')
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(op['name'])
        
        return grouped
    
    def get_operators_by_type(self) -> Dict[str, List[Dict]]:
        """按类型分组操作符（如 TS:Transform, CrossSection:Standardize）"""
        operators = self.load_operators()
        grouped = {}
        
        for op in operators:
            op_type = op.get('type', 'Other')
            if op_type not in grouped:
                grouped[op_type] = []
            grouped[op_type].append(op)
        
        return grouped
    
    def get_field_ids(self) -> List[str]:
        """获取所有字段 ID"""
        fields = self.load_fields()
        return [field['id'] for field in fields]
    
    def get_fields_by_type(self) -> Dict[str, List[str]]:
        """按类型分组字段（MATRIX, VECTOR, SCALAR）"""
        fields = self.load_fields()
        grouped = {}
        
        for field in fields:
            field_type = field.get('type', 'UNKNOWN')
            if field_type not in grouped:
                grouped[field_type] = []
            grouped[field_type].append(field['id'])
        
        return grouped
    
    def get_fields_by_dataset(self) -> Dict[str, List[Dict]]:
        """按数据集分组字段"""
        self.load_fields()  # 确保已加载
        return self._fields_by_dataset or {}
    
    def search_operators(self, keyword: str) -> List[Dict]:
        """搜索操作符（按名称或描述）"""
        operators = self.load_operators()
        keyword_lower = keyword.lower()
        
        results = []
        for op in operators:
            if (keyword_lower in op.get('name', '').lower() or
                keyword_lower in op.get('description', '').lower() or
                keyword_lower in op.get('definition', '').lower()):
                results.append(op)
        
        return results
    
    def search_fields(self, keyword: str) -> List[Dict]:
        """搜索字段（按 ID 或描述）"""
        fields = self.load_fields()
        keyword_lower = keyword.lower()
        
        results = []
        for field in fields:
            if (keyword_lower in field.get('id', '').lower() or
                keyword_lower in field.get('description', '').lower()):
                results.append(field)
        
        return results
    
    def get_operator_info(self, operator_name: str) -> Dict:
        """获取特定操作符的详细信息"""
        operators = self.load_operators()
        for op in operators:
            if op['name'] == operator_name:
                return op
        return {}
    
    def get_field_info(self, field_id: str) -> Dict:
        """获取特定字段的详细信息"""
        fields = self.load_fields()
        for field in fields:
            if field['id'] == field_id:
                return field
        return {}
    
    def validate_expression(self, expression: str) -> Dict[str, any]:
        """
        验证表达式中的操作符和字段是否有效
        
        Returns:
            {
                'valid': bool,
                'unknown_operators': List[str],
                'unknown_fields': List[str],
                'used_operators': List[str],
                'used_fields': List[str]
            }
        """
        import re
        
        # 提取表达式中的函数名（操作符）
        operator_pattern = r'(\w+)\('
        used_operators = re.findall(operator_pattern, expression)
        
        # 提取字段 ID（通常是小写字母、数字和下划线）
        field_pattern = r'\b([a-z][a-z0-9_]*)\b'
        potential_fields = re.findall(field_pattern, expression)
        
        # 获取有效的操作符和字段
        valid_operators = set(self.get_operator_names())
        valid_fields = set(self.get_field_ids())
        
        # 过滤出实际使用的字段（排除操作符和关键字）
        reserved_words = {'and', 'or', 'not', 'true', 'false', 'if', 'else', 'return'}
        used_fields = [f for f in potential_fields 
                      if f in valid_fields and f not in valid_operators and f not in reserved_words]
        
        # 找出未知的操作符和字段
        unknown_operators = [op for op in used_operators if op not in valid_operators]
        unknown_fields = [f for f in used_fields if f not in valid_fields]
        
        return {
            'valid': len(unknown_operators) == 0 and len(unknown_fields) == 0,
            'unknown_operators': unknown_operators,
            'unknown_fields': unknown_fields,
            'used_operators': list(set(used_operators)),
            'used_fields': list(set(used_fields))
        }
    
    def format_operators_for_llm(self, max_per_category: int = 10) -> str:
        """
        格式化操作符为 LLM 友好的格式
        
        Args:
            max_per_category: 每个类别最多显示的操作符数量
        """
        operators_by_cat = self.get_operators_by_category()
        
        output = ["# Available Operators\n"]
        
        for category, op_names in sorted(operators_by_cat.items()):
            output.append(f"\n## {category}")
            
            for i, op_name in enumerate(op_names[:max_per_category]):
                op_info = self.get_operator_info(op_name)
                definition = op_info.get('definition', '')
                description = op_info.get('description', '')
                output.append(f"- **{op_name}**: {definition} — {description}")
            
            if len(op_names) > max_per_category:
                output.append(f"  ... (+{len(op_names) - max_per_category} more)")
        
        return "\n".join(output)
    
    def format_fields_for_llm(self, max_per_dataset: int = 10) -> str:
        """
        格式化字段为 LLM 友好的格式
        
        Args:
            max_per_dataset: 每个数据集最多显示的字段数量
        """
        fields_by_dataset = self.get_fields_by_dataset()
        
        output = ["# Available Data Fields\n"]
        
        for dataset, fields in sorted(fields_by_dataset.items()):
            output.append(f"\n## Dataset: {dataset} ({len(fields)} fields)")
            
            for i, field in enumerate(fields[:max_per_dataset]):
                field_id = field['id']
                field_type = field.get('type', 'UNKNOWN')
                description = field.get('description', '')
                output.append(f"- **{field_id}** ({field_type}): {description}")
            
            if len(fields) > max_per_dataset:
                output.append(f"  ... (+{len(fields) - max_per_dataset} more)")
        
        return "\n".join(output)

