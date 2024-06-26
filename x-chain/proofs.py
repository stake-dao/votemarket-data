from web3 import Web3
from w3multicall.multicall import W3Multicall
import json, os, requests, rlp
from hexbytes import HexBytes
from dotenv import load_dotenv
from eth_abi import encode
from eth_utils import keccak

load_dotenv()

MAINNET_URL = "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("ALCHEMY_API_KEY")
ARBITRUM_URL = "https://arb1.arbitrum.io/rpc"
OPTIMISM_URL = "https://optimism.llamarpc.com"
BASE_URL = "https://base.llamarpc.com"
POLYGON_URL = "https://polygon.llamarpc.com"


ETHEREUM_STATE_SENDER = "0x189B2c0e4e8e221173f266f311C949498A4859D1"
AGNOSTIC_ENDPOINT = os.getenv("AGNOSTIC_ENDPOINT")
AGNOSTIC_HEADERS = {
    "Authorization": os.getenv("AGNOSTIC_API_KEY"),
    "Cache-Control": "max-age=300",
}

# To get positions
GAUGES_SLOTS = {
    "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD": {
        "last_user_vote": 1000000007,
        "point_weights": 1000000008,
        "vote_user_slope": 1000000005,
    },
    "0x3669C421b77340B2979d1A00a792CC2ee0FcE737": {
        "last_user_vote": 1000000010,
        "point_weights": 10000000011,
        "vote_user_slope": 1000000008,
    },
    "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37": {
        "last_user_vote": 1000000010,
        "point_weights": 10000000011,
        "vote_user_slope": 1000000008,
    },
}


def get_web3(chainId):
    if chainId == 1:
        return Web3(Web3.HTTPProvider(MAINNET_URL))
    elif chainId == 42161:
        return Web3(Web3.HTTPProvider(ARBITRUM_URL))
    elif chainId == 10:
        return Web3(Web3.HTTPProvider(OPTIMISM_URL))
    elif chainId == 137:
        return Web3(Web3.HTTPProvider(POLYGON_URL))
    else:
        return Web3(Web3.HTTPProvider(BASE_URL))


def load_json(name):
    with open(name + ".json", "r") as f:
        return json.load(f)


def load_contract(w3, address, abi):
    return w3.eth.contract(
        address=Web3.toChecksumAddress(address),
        abi=abi,
    )


def encode_rlp_proofs(proofs):
    account_proof = list(map(rlp.decode, map(HexBytes, proofs["accountProof"])))
    storage_proofs = [
        list(map(rlp.decode, map(HexBytes, proof["proof"])))
        for proof in proofs["storageProof"]
    ]
    return rlp.encode([account_proof, *storage_proofs])


def get_event_logs(
    w3, contract_address, abi, event_name, from_block, to_block, filters=None
):
    contract_address = Web3.toChecksumAddress(contract_address.lower())
    contract = w3.eth.contract(address=contract_address, abi=load_json(abi))
    return getattr(contract.events, event_name).getLogs(
        fromBlock=from_block, toBlock=to_block, argument_filters=filters
    )


def get_active_bounties(vm, current_period, w3):
    active_bounties = []
    nextId = vm.functions.nextID().call()
    multicall = W3Multicall(w3)

    # Prepare multicall for all bounties
    for i in range(nextId):
        multicall.add(
            W3Multicall.Call(
                vm.address,
                "bounties(uint256)(address,address,address,uint256,uint256,uint256,uint256)",
                [i],
            )
        )
        multicall.add(
            W3Multicall.Call(
                vm.address,
                "upgradeBountyQueue(uint256)(uint256,uint256,uint256,uint256)",
                [i],
            )
        )
        multicall.add(
            W3Multicall.Call(
                vm.address, "getBlacklistedAddressesPerBounty(uint256)(address[])", [i]
            )
        )

    # Execute all calls in a single batch
    results = multicall.call()

    # Process results
    for i in range(nextId):
        bounty_details = results[i * 3]
        upgrade_details = results[i * 3 + 1]
        blacklist = results[i * 3 + 2]

        bounty_endTimestamp = bounty_details[4]
        upgraded_bounty_endTimestamp = upgrade_details[3]

        if (
            bounty_endTimestamp > current_period
            or upgraded_bounty_endTimestamp > current_period
        ):
            active_bounties.append(
                {
                    "bountyId": i,
                    "rewardToken": bounty_details[2],
                    "gaugeAddress": bounty_details[0],
                    "blacklist": blacklist,
                }
            )

    return active_bounties


def query_all_voters_gauges(gauge_controller, gauge_addresses):
    # Fetch votes
    gaugesString = "'" + "','".join(str(s) for s in gauge_addresses) + "'"

    # Get all voters
    query = """
                                select 
                                    input_1_value_address as user,
                                    input_2_value_address as gauge
                                from evm_events_ethereum_mainnet 
                                WHERE 
                                    address IN ('{gauge_controller}') and 
                                    input_2_value_address IN ({gauges}) and 
                                    signature = 'VoteForGauge(uint256,address,address,uint256)' 
                                GROUP BY user, gauge
                            """.format(
        gauge_controller=gauge_controller,
        gauges=gaugesString,
    )
    agnosticResponse = requests.post(
        AGNOSTIC_ENDPOINT, headers=AGNOSTIC_HEADERS, data=query
    )
    if agnosticResponse.status_code != 200:
        print("Error fetching voters from Agnostic")
        return []
    rowsVoted = agnosticResponse.json()["rows"]

    grouped_data = {}

    for user, gauge in rowsVoted:
        if gauge not in grouped_data:
            grouped_data[gauge] = []
        grouped_data[gauge].append(user)

    return grouped_data


def check_eligibility(w3, gauge_controller, user, gauge_address, current_period):
    # Check if user is eligible for the bounty
    is_eligible = False

    """
    # Check if user is blacklisted on all bounties with that gauge, if not , process
    for bounty in active_bounties:
        if bounty.get("gaugeAddress") == gauge:
            if user not in bounty.get("blacklist"):
                is_eligible = True
                break
    """

    # Check the slope of that user for the gauge
    last_vote = gauge_controller.functions.last_user_vote(
        w3.toChecksumAddress(user.lower()), w3.toChecksumAddress(gauge_address.lower())
    ).call()
    (slope, power, end) = gauge_controller.functions.vote_user_slopes(
        w3.toChecksumAddress(user.lower()), w3.toChecksumAddress(gauge_address.lower())
    ).call()

    if slope != 0 and current_period < end and current_period > last_vote:
        is_eligible = True

    return is_eligible



def get_position_from_user_gauge(user, gauge, base_slot):
    # Encode the user address with the base slot and hash
    user_encoded = keccak(encode(["uint256", "address"], [base_slot, user]))

    # Encode the result with the gauge address and hash
    final_slot = keccak(encode(["bytes32", "address"], [user_encoded, gauge]))

    # Convert the final hash to an integer slot number
    return int.from_bytes(final_slot, byteorder="big")


def get_position_from_gauge_time(gauge, time, base_slot):
    # Encode the user address with the base slot and hash
    gauge_encoded = keccak(encode(["uint256", "address"], [base_slot, gauge]))

    # Encode the result with the user address and time
    final_slot = keccak(encode(["bytes32", "uint256"], [gauge_encoded, time]))

    # Convert the final hash to an integer slot number
    return int.from_bytes(final_slot, byteorder="big")



def main():
    # Get input data
    input_data = load_json("x-chain/inputs")

    # Get web3 instance on Ethereum
    w3_eth = get_web3(1)

    gauge_abi = load_json("abi/GaugeController")
    platform_l2_abi = load_json("abi/PlatformL2")
    state_sender_abi = load_json("abi/StateSender")

    state_sender = load_contract(w3_eth, ETHEREUM_STATE_SENDER, state_sender_abi)
    current_period = state_sender.functions.getCurrentPeriod().call()

    protocol_data = {}

    # Protocol loop
    for line in input_data:
        protocol = line["protocol"]
        gauge_controller = line["gauge_controller"]
        start_block = line["start_block"]
        platforms = line["platforms"]
        use_state_sender = line["use_state_sender"]

        protocol_data[protocol] = {}

        # Load gauge controller contract from Mainnet
        gauge_controller_contract = load_contract(w3_eth, gauge_controller, gauge_abi)

        active_bounties = []  # {bountyId; gaugeAdress}

        for row in platforms:
            w3 = get_web3(row["chainId"])
            vm = load_contract(w3, row["address"], platform_l2_abi)
            active_bounties = active_bounties + get_active_bounties(
                vm, current_period, w3
            )

        all_gauges = [
            w3.toChecksumAddress(bounty["gaugeAddress"].lower())
            for bounty in active_bounties
        ]

        if len(all_gauges) == 0:
            continue

        all_voters = query_all_voters_gauges(gauge_controller, all_gauges)

        all_users = {}

        # Now , check for each voter if he has vote (eligible for bounty) on the gauge
        for gauge_address, voters in all_voters.items():
            if not all_users.get(gauge_address):
                all_users[gauge_address] = []
            for user in voters:
                if check_eligibility(
                    w3_eth,
                    gauge_controller_contract,
                    user,
                    gauge_address,
                    current_period,
                ):
                    all_users[gauge_address].append(user)

        # Generate proofs for all users eligible for claims (to be used on claims) -> Stored as gauge -> user -> proofs
        latest_header_proof = load_json(
            f"bounties/x-chain/{current_period}/block_header"
        )

        user_proofs_rlp = {}  # gauge -> user -> proofs[]

        for gauge_address, users in all_users.items():
            user_proofs_rlp[gauge_address] = user_proofs_rlp.get(gauge_address, {})
            for user in users:
                positions = []
                if user not in user_proofs_rlp[gauge_address]:
                    # Generate main proof (for user)
                    if use_state_sender:
                        main_proof_params = (
                            state_sender.functions.generateEthProofParams(
                                w3_eth.toChecksumAddress(user.lower()),
                                w3_eth.toChecksumAddress(gauge_address.lower()),
                                current_period,
                            ).call()
                        )
                        for position in main_proof_params[3]:
                            positions.append(w3_eth.toHex(position))
                    else:
                        # Positions array : [lastUserVotes; pointWeights.bias; pointsWeigths.slope; voteUserSlope.slope; voteUserSlope.power; voteUserSlope.end]
                        last_user_vote_base_slot = GAUGES_SLOTS[gauge_controller][
                            "last_user_vote"
                        ]
                        point_weights_base_slot = GAUGES_SLOTS[gauge_controller][
                            "point_weights"
                        ]
                        vote_user_slope_base_slot = GAUGES_SLOTS[gauge_controller][
                            "vote_user_slope"
                        ]

                        last_user_vote_position = get_position_from_user_gauge(
                            w3_eth.toChecksumAddress(user.lower()), w3_eth.toChecksumAddress(gauge_address.lower()), last_user_vote_base_slot
                        )
                        point_weights_position = get_position_from_gauge_time(
                            w3_eth.toChecksumAddress(gauge_address.lower()), current_period, point_weights_base_slot
                        )
                        vote_user_slope_position = get_position_from_user_gauge(
                            w3_eth.toChecksumAddress(user.lower()), w3_eth.toChecksumAddress(gauge_address.lower()), vote_user_slope_base_slot
                        )

                        vote_user_slope_slope = vote_user_slope_position
                        vote_user_slope_power = vote_user_slope_position + 1
                        vote_user_slope_end = vote_user_slope_position + 2

                        points_weights_bias = point_weights_position
                        points_weights_slope = point_weights_position + 1

                        positions.append(w3_eth.toHex(last_user_vote_position))
                        positions.append(w3_eth.toHex(points_weights_bias))
                        positions.append(w3_eth.toHex(points_weights_slope))
                        positions.append(w3_eth.toHex(vote_user_slope_slope))
                        positions.append(w3_eth.toHex(vote_user_slope_power))
                        positions.append(w3_eth.toHex(vote_user_slope_end))

                    # Proof rlp
                    raw_proof_data = w3_eth.eth.get_proof(
                        w3_eth.toChecksumAddress(gauge_controller.lower()),
                        positions,
                        hex(latest_header_proof["BlockNumber"]),
                    )
                    rlp_proof = encode_rlp_proofs(raw_proof_data)
                    user_proofs_rlp[gauge_address][user] = rlp_proof.hex()

        # Add blacklisted addresses to the proofs
        for bounty in active_bounties:
            gauge_address = w3_eth.toChecksumAddress(bounty["gaugeAddress"].lower())

            if len(bounty["blacklist"]) == 0:
                continue
            for user in bounty["blacklist"]:
                if w3_eth.toChecksumAddress(user.lower()) not in user_proofs_rlp.get(
                    gauge_address, {}
                ):
                    positions = []
                    if use_state_sender:
                        main_proof_params = state_sender.functions.generateEthProofParams(
                        w3_eth.toChecksumAddress(user.lower()),
                        gauge_address,
                        current_period,
                        ).call()
                        for position in main_proof_params[3]:
                            positions.append(w3_eth.toHex(position))
                    else:
                        # Positions array : [lastUserVotes; pointWeights.bias; pointsWeigths.slope; voteUserSlope.slope; voteUserSlope.power; voteUserSlope.end]
                        last_user_vote_base_slot = GAUGES_SLOTS[w3_eth.toChecksumAddress(gauge_controller.lower())][
                            "last_user_vote"
                        ]
                        point_weights_base_slot = GAUGES_SLOTS[w3_eth.toChecksumAddress(gauge_controller.lower())][
                            "point_weights"
                        ]
                        vote_user_slope_base_slot = GAUGES_SLOTS[w3_eth.toChecksumAddress(gauge_controller.lower())][
                            "vote_user_slope"
                        ]

                        last_user_vote_position = get_position_from_user_gauge(
                            w3_eth.toChecksumAddress(user.lower()), w3_eth.toChecksumAddress(gauge_address.lower()), last_user_vote_base_slot
                        )
                        point_weights_position = get_position_from_gauge_time(
                            w3_eth.toChecksumAddress(gauge_address.lower()), current_period, point_weights_base_slot
                        )
                        vote_user_slope_position = get_position_from_user_gauge(
                            w3_eth.toChecksumAddress(user.lower()), w3_eth.toChecksumAddress(gauge_address.lower()), vote_user_slope_base_slot
                        )

                        vote_user_slope_slope = vote_user_slope_position
                        vote_user_slope_power = vote_user_slope_position + 1
                        vote_user_slope_end = vote_user_slope_position + 2

                        points_weights_bias = point_weights_position
                        points_weights_slope = point_weights_position + 1

                        positions.append(w3_eth.toHex(last_user_vote_position))
                        positions.append(w3_eth.toHex(points_weights_bias))
                        positions.append(w3_eth.toHex(points_weights_slope))
                        positions.append(w3_eth.toHex(vote_user_slope_slope))
                        positions.append(w3_eth.toHex(vote_user_slope_power))
                        positions.append(w3_eth.toHex(vote_user_slope_end))

                    # Proof rlp
                    raw_proof_data = w3_eth.eth.get_proof(
                        w3_eth.toChecksumAddress(gauge_controller.lower()),
                        positions,
                        hex(latest_header_proof["BlockNumber"]),
                    )
                    rlp_proof = encode_rlp_proofs(raw_proof_data)
                    user_proofs_rlp[gauge_address][user] = rlp_proof.hex()

        protocol_data[protocol] = user_proofs_rlp


    # Write result to a JSON file
    directory = f"bounties/x-chain/{current_period}"
    if not os.path.exists(directory):
        os.makedirs(directory)

    for protocol, proofs in protocol_data.items():
        if len(proofs) > 0:
            with open(f"{directory}/{protocol}_proofs.json", "w") as f:
                json.dump(proofs, f)


if __name__ == "__main__":
    main()
