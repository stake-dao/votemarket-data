import subprocess, json, logging
from web3 import Web3

"""
Fetch block submited on Oracle for week and parse header and data as RLP
"""

logging.basicConfig(level=logging.INFO)


def load_json(name):
    with open("abi/" + name + ".json", "r") as f:
        return json.load(f)


def main():
    w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
    if w3.isConnected() == False:
        logging.error("RPC down")
        return

    state_sender_abi = load_json("StateSender")

    # Block hash tooked from the contract, period logic already handled
    state_sender = w3.eth.contract(
        address=Web3.toChecksumAddress("0xC19d317c84e43F93fFeBa146f4f116A6F2B04663"),
        abi=state_sender_abi,
    )

    # Get current period
    current_period = state_sender.functions.getCurrentPeriod().call()

    # Submit current period to get latest block
    block_number = state_sender.functions.blockNumbers(current_period).call()

    # If no block , error
    if block_number == 0:
        print(f"Error: No block for period {current_period}")
        return
    toji_output = run_toji("https://eth.llamarpc.com", block_number)
    parsed_data = parse_toji_output(toji_output)

    # Add block number in a field in the parsed data
    parsed_data["Block Number"] = block_number
    # Add block date (timestamp) in a field in the parsed data
    parsed_data["Block Timestamp"] = w3.eth.get_block(block_number).timestamp
    # Transforming keys to camelCase
    camel_case_data = {to_camel_case(key): value for key, value in parsed_data.items()}
    # Convert the dictionary to JSON
    json_data = json.dumps(camel_case_data, indent=4)

    logging.info(f"Block {block_number} data: {json_data}")

    # Write result to a JSON file
    with open("bounties/ethBlockData.json", "w") as file:
        file.write(json_data)


def parse_toji_output(data):
    # Initialize an empty dictionary to hold the parsed data
    parsed_data = {}

    # Split the data into lines and iterate over each line
    lines = data.split("\n")
    for line in lines:
        # Check if line is not empty
        if line.strip() != "":
            # Split the line by the first occurrence of ":", which separates the key and value
            parts = line.split(":", 1)
            if len(parts) == 2:  # Ensure there are two parts
                key = parts[0].strip()  # Strip whitespace from the key
                value = (
                    parts[1].strip().replace('"', "")
                )  # Strip whitespace from the value and remove "
                parsed_data[key] = value

    return parsed_data


def to_camel_case(snake_str):
    components = snake_str.split(" ")
    return "".join(x.capitalize() for x in components)


def run_toji(url, block_number):
    # Construct the command as a list of arguments
    command = ["toji", "-r", url, "-n", str(block_number)]

    # Run the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Check if the command was successful
    if result.returncode == 0:
        # Command was successful, process result.stdout
        return result.stdout
    else:
        # There was an error
        return result.stderr


if __name__ == "__main__":
    main()
