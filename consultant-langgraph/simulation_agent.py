"""
Simulation Agent - Submits alphas to WorldQuant Brain API for testing
"""

import requests
import time
import json
from typing import Dict, List, Optional
from datetime import datetime
from requests.auth import HTTPBasicAuth
from pathlib import Path

from base_agent import BaseAgent


class SimulationAgent(BaseAgent):
    """
    Agent responsible for submitting alpha expressions to WorldQuant Brain API
    and retrieving simulation results
    """
    
    def __init__(self, credentials_path: str, config: Optional[Dict] = None):
        """
        Initialize Simulation Agent
        
        Args:
            credentials_path: Path to WorldQuant credentials file
            config: Optional configuration dict
        """
        super().__init__('simulation_agent', config)
        
        self.credentials_path = credentials_path
        self.sess = requests.Session()
        self.setup_auth()
        
        # Simulation settings
        self.default_settings = self.config.get('simulation_settings', {
            'instrumentType': 'EQUITY',
            'region': 'USA',
            'universe': 'TOP3000',
            'delay': 1,
            'decay': 0,
            'neutralization': 'SUBINDUSTRY',
            'truncation': 0.08,
            'pasteurization': 'ON',
            'unitHandling': 'VERIFY',
            'nanHandling': 'OFF',
            'language': 'FASTEXPR',
            'visualization': False
        })
        
        # API settings
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 2)
        self.poll_interval = self.config.get('poll_interval', 5)
        self.timeout = self.config.get('timeout', 60)
    
    def setup_auth(self):
        """Setup authentication for WorldQuant Brain API"""
        try:
            # Load credentials (support both JSON and text format)
            with open(self.credentials_path, 'r') as f:
                content = f.read().strip()
                
            # Try JSON format first (e.g., ["email", "password"])
            try:
                credentials = json.loads(content)
                email, password = credentials
            except json.JSONDecodeError:
                # Fall back to text format (line-by-line)
                lines = content.split('\n')
                email = lines[0].strip()
                password = lines[1].strip()
            
            self.sess.auth = HTTPBasicAuth(email, password)
            
            # Critical step: POST to /authentication endpoint to get session token
            self.logger.info("Authenticating with WorldQuant Brain...")
            response = self.sess.post('https://api.worldquantbrain.com/authentication')
            
            if response.status_code != 201:
                raise Exception(f"Authentication failed: {response.text}")
            
            self.logger.info("Authentication successful")
        except Exception as e:
            self.logger.error(f"Failed to setup authentication: {e}")
            raise
    
    def run(self, expressions: List[Dict]) -> List[Dict]:
        """
        Main execution: simulate a batch of alpha expressions
        
        Args:
            expressions: List of expression dicts from FactorAgent
        
        Returns:
            List of simulation result dicts
        """
        self.logger.info(f"Starting simulation for {len(expressions)} expressions")
        start_time = datetime.now()
        
        results = []
        for expr in expressions:
            result = self.simulate_single(expr)
            results.append(result)
            
            # Rate limiting
            time.sleep(0.5)
        
        self.log_execution_time(start_time, "Simulation batch")
        self.logger.info(f"Completed: {sum(1 for r in results if r.get('status') == 'success')}/{len(results)} successful")
        
        # Save results
        self.save_json(results, 'data/simulation_results.json')
        
        return results
    
    def simulate_single(self, expression_data: Dict) -> Dict:
        """
        Simulate a single alpha expression
        
        Args:
            expression_data: Dict with 'expression_id', 'expression', etc.
        
        Returns:
            Simulation result dict
        """
        expression = expression_data.get('expression')
        expr_id = expression_data.get('expression_id')
        
        self.logger.info(f"Simulating {expr_id}: {expression[:80]}...")
        
        try:
            # Submit alpha for simulation
            progress_url = self._submit_alpha(expression)
            
            if not progress_url:
                return self._create_error_result(expr_id, expression, "Failed to submit alpha")
            
            # Wait for simulation to complete (poll progress URL)
            result = self._wait_for_result(progress_url)
            
            if result:
                result['expression_id'] = expr_id
                result['expression'] = expression
                result['status'] = 'success'
                result['timestamp'] = self.get_timestamp()
                
                self.logger.info(
                    f"{expr_id}: Sharpe={result.get('sharpe', 0):.3f}, "
                    f"Fitness={result.get('fitness', 0):.3f}"
                )
                return result
            else:
                return self._create_error_result(expr_id, expression, "Simulation timeout")
        
        except Exception as e:
            self.logger.error(f"Error simulating {expr_id}: {e}")
            return self._create_error_result(expr_id, expression, str(e))
    
    def _submit_alpha(self, expression: str) -> Optional[str]:
        """
        Submit an alpha expression to WorldQuant Brain
        
        Args:
            expression: Alpha expression string
        
        Returns:
            Alpha ID if successful, None otherwise
        """
        url = 'https://api.worldquantbrain.com/simulations'
        
        payload = {
            'type': 'REGULAR',
            'regular': expression,
            'settings': self.default_settings
        }
        
        for attempt in range(self.max_retries):
            try:
                response = self.sess.post(url, json=payload, timeout=30)
                
                # Log response for debugging
                self.logger.debug(f"Submit response: status={response.status_code}, body={response.text[:200]}")
                
                if response.status_code == 201:
                    # WorldQuant API returns 201 with empty body
                    # The actual progress URL is in the Location header
                    progress_url = response.headers.get('Location')
                    
                    if not progress_url:
                        self.logger.error("No Location header in 201 response")
                        return None
                    
                    self.logger.debug(f"Got progress URL: {progress_url}")
                    return progress_url  # Return progress URL, not alpha_id
                
                elif response.status_code == 400:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('detail', str(error_data))
                    except:
                        error_msg = response.text
                    self.logger.warning(f"Syntax error: {error_msg}")
                    return None
                
                elif response.status_code == 403:
                    self.logger.error("Permission denied - quota exceeded?")
                    return None
                
                else:
                    self.logger.warning(f"Submit failed (attempt {attempt+1}): {response.status_code}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
            
            except Exception as e:
                # Try to log response details before the exception
                try:
                    self.logger.error(f"Submit exception (attempt {attempt+1}): {e}")
                    if 'response' in locals():
                        self.logger.error(f"Response status: {response.status_code}, body: {response.text[:500]}")
                except:
                    self.logger.error(f"Submit exception (attempt {attempt+1}): {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        return None
    
    def _wait_for_result(self, progress_url: str) -> Optional[Dict]:
        """
        Poll progress URL for simulation results
        
        Args:
            progress_url: Progress URL from Location header
        
        Returns:
            Result dict if successful, None otherwise
        """
        start_time = time.time()
        poll_count = 0
        
        self.logger.info(f"Polling progress URL: {progress_url}")
        
        while time.time() - start_time < self.timeout:
            try:
                response = self.sess.get(progress_url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')
                    progress = data.get('progress', 0)
                    
                    poll_count += 1
                    self.logger.debug(f"Poll #{poll_count}: status={status}, progress={progress}%")
                    
                    # Check if simulation is complete
                    if status == 'COMPLETE':
                        alpha_id = data.get('alpha')
                        is_data = data.get('is', {})
                        
                        self.logger.info(f"Simulation complete! Alpha ID: {alpha_id}")
                        
                        return {
                            'alpha_id': alpha_id,
                            'sharpe': is_data.get('sharpe', 0),
                            'fitness': is_data.get('fitness', 0),
                            'returns': is_data.get('returns', 0),
                            'turnover': is_data.get('turnover', 0),
                            'drawdown': is_data.get('drawdown', 0),
                            'margin': is_data.get('margin', 0),
                            'longCount': is_data.get('longCount', 0),
                            'shortCount': is_data.get('shortCount', 0)
                        }
                    
                    elif status == 'ERROR':
                        error_msg = data.get('error', 'Simulation failed')
                        error_detail = data.get('details', data.get('message', ''))
                        self.logger.error(f"Simulation ERROR: {error_msg}")
                        if error_detail:
                            self.logger.error(f"Error details: {error_detail}")
                        self.logger.debug(f"Full error response: {data}")
                        return None
                    
                    # Still processing (RUNNING, PENDING, etc.)
                    time.sleep(self.poll_interval)
                
                else:
                    self.logger.warning(f"Poll failed: {response.status_code}")
                    time.sleep(self.poll_interval)
            
            except Exception as e:
                self.logger.error(f"Poll exception: {e}")
                time.sleep(self.poll_interval)
        
        self.logger.error(f"Timeout waiting for simulation result (>{self.timeout}s)")
        return None
    
    def _create_error_result(self, expr_id: str, expression: str, error_msg: str) -> Dict:
        """
        Create an error result dict
        
        Args:
            expr_id: Expression ID
            expression: Alpha expression
            error_msg: Error message
        
        Returns:
            Error result dict
        """
        return {
            'expression_id': expr_id,
            'expression': expression,
            'status': 'error',
            'error': error_msg,
            'sharpe': -999,
            'fitness': 0,
            'timestamp': self.get_timestamp()
        }

