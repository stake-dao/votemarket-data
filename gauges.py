#!/usr/bin/env python3
"""Fetch gauge data from various DeFi protocols."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
GAUGES_DIR = Path("./gauges")
TIMEOUT = 30  # seconds

# Protocol configurations
PROTOCOLS = {
    "curve": {
        "url": "https://api.curve.finance/api/getAllGauges",
        "method": "GET",
        "output_file": "curve.json"
    },
    "frax": {
        "url": "https://api.frax.finance/v1/gauge/voter-info/0x0000000000000000000000000000000000000000",
        "method": "GET",
        "output_file": "frax.json"
    },
    "fxn": {
        "url": "https://api.aladdin.club/api1/get_fx_gauge_list",
        "method": "GET",
        "output_file": "fxn.json"
    },
    "balancer": {
        "url": "https://api-v3.balancer.fi/",
        "method": "POST",
        "output_file": "balancer.json",
        "query": """
            query {
              veBalGetVotingList {
                gauge {
                    address
                    isKilled
                }
                symbol
                chain
              }
            }
        """
    }
}


class GaugeFetcher:
    """Fetches gauge data from various DeFi protocols."""
    
    def __init__(self, gauges_dir: Path = GAUGES_DIR):
        self.gauges_dir = gauges_dir
        self.gauges_dir.mkdir(exist_ok=True)
        
    def write_gauges(self, data: Any, filename: str) -> None:
        """Write gauge data to a JSON file."""
        output_path = self.gauges_dir / filename
        try:
            with open(output_path, "w") as f:
                json.dump(data, f, indent=4)
            logger.info(f"Successfully wrote gauge data to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write gauge data to {output_path}: {e}")
            raise
    
    def fetch_simple(self, url: str, output_file: str) -> bool:
        """Fetch data from a simple GET endpoint."""
        try:
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            self.write_gauges(data, output_file)
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch data from {url}: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from {url}: {e}")
            return False
    
    def fetch_balancer(self) -> bool:
        """Fetch Balancer gauge data using GraphQL."""
        config = PROTOCOLS["balancer"]
        
        try:
            response = requests.post(
                config["url"],
                json={"query": config["query"]},
                timeout=TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            if data and "data" in data and "veBalGetVotingList" in data["data"]:
                self.write_gauges(data["data"]["veBalGetVotingList"], config["output_file"])
                return True
            else:
                logger.error("Failed to fetch Balancer pools: Invalid response structure")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Balancer pools: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Balancer response: {e}")
            return False
    
    def fetch_all(self) -> Dict[str, bool]:
        """Fetch gauge data from all configured protocols."""
        results = {}
        
        for protocol, config in PROTOCOLS.items():
            logger.info(f"Fetching {protocol} gauge data...")
            
            if protocol == "balancer":
                results[protocol] = self.fetch_balancer()
            else:
                results[protocol] = self.fetch_simple(config["url"], config["output_file"])
                
        return results


def main():
    """Main function to fetch all gauge data."""
    fetcher = GaugeFetcher()
    results = fetcher.fetch_all()
    
    # Summary
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    logger.info(f"\nFetch complete: {successful}/{total} protocols succeeded")
    
    if successful < total:
        failed = [protocol for protocol, success in results.items() if not success]
        logger.warning(f"Failed protocols: {', '.join(failed)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())