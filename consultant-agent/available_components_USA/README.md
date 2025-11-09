# WorldQuant Brain - Available Components (USA)

**Generated:** 2025-11-02  
**Region:** USA

---

## 📊 Summary

- **4,035** Data Fields across **16** Datasets
- **66** Operators (3 marked as commonly used wrappers)

---

## 📁 Files

```
available_components_USA/
├── SUMMARY.txt       (3 KB  - Quick statistics & wrapper list)
├── operators.txt     (14 KB - All operators with [WRAPPER] tags)
└── fields/           (590 KB total - 16 dataset files)
    ├── fundamental6.txt  (992 fields)
    ├── model77.txt       (1,546 fields) 🔥 Largest
    ├── analyst4.txt      (387 fields)
    └── ... (13 more)
```

---

## 🚀 Quick Start

### View Summary
```bash
cat SUMMARY.txt
```

### Browse Operators
```bash
# See all operators
cat operators.txt

# Find wrappers
grep "\[WRAPPER\]" operators.txt
```

### Browse Fields by Dataset
```bash
# List all datasets
ls fields/

# View specific dataset
cat fields/fundamental6.txt
cat fields/model77.txt
```

### Search
```bash
# Search in all fields
grep -i "income" fields/*.txt

# Search for specific operator
grep "ts_rank" operators.txt
```

---

## 📚 Datasets

| Category | Files | Fields |
|----------|-------|--------|
| **Fundamental** | `fundamental2.txt`, `fundamental6.txt` | 1,310 |
| **Models** | `model16.txt`, `model51.txt`, `model77.txt` | 1,570 |
| **News/Sentiment** | `news12.txt`, `news18.txt`, `sentiment1.txt`, `socialmedia*` | 434 |
| **Market** | `pv1.txt`, `pv13.txt`, `option8.txt`, `option9.txt` | 329 |
| **Analyst** | `analyst4.txt` | 387 |

---

## 💡 Wrappers

These operators (marked with `[WRAPPER]` in operators.txt) are commonly used to wrap other operators:

- `winsorize` - Trim extreme values
- `ts_backfill` - Fill missing values
- `ts_scale` - Scale to [0, 1] range

**Example usage:**
```
winsorize(ts_std_dev(close, 60), std=4)
ts_backfill(fundamental_field, 20)
```

---

## 🔄 Update Data

To regenerate with latest from WorldQuant Brain API:

```bash
cd consultant-multi-arm-bandit-ollama
python export_available_components.py
```

---

**Note:** This directory does NOT include large JSON files for better performance.  
All data is organized in small, readable text files.
