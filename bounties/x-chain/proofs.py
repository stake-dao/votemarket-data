import json, os, logging
from eth_abi import encode
from eth_utils import keccak
from utils import Utils, Constants

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)


def generate_proof(
    w3_eth, protocol, gauge_address, user, current_period, latest_header_proof
):
    logging.info("Protocol: " + protocol)
    logging.info("Proof generation for user: " + user + " on gauge: " + gauge_address)

    # Positions array : [lastUserVotes; pointWeights.bias; pointsWeigths.slope; voteUserSlope.slope; voteUserSlope.power; voteUserSlope.end]
    positions = []
    last_user_vote_base_slot = Constants.GAUGES_SLOTS[protocol]["last_user_vote"]
    point_weights_base_slot = Constants.GAUGES_SLOTS[protocol]["point_weights"]
    vote_user_slope_base_slot = Constants.GAUGES_SLOTS[protocol]["vote_user_slope"]

    last_user_vote_position = get_position_from_user_gauge(
        w3_eth.toChecksumAddress(user.lower()),
        w3_eth.toChecksumAddress(gauge_address.lower()),
        last_user_vote_base_slot,
    )

    if protocol == "curve":
        point_weights_position = get_position_from_gauge_time_old(
            w3_eth.toChecksumAddress(gauge_address.lower()),
            current_period,
            point_weights_base_slot,
        )
        vote_user_slope_position = get_position_from_user_gauge_old(
            w3_eth.toChecksumAddress(user.lower()),
            w3_eth.toChecksumAddress(gauge_address.lower()),
            vote_user_slope_base_slot,
        )

    else:
        point_weights_position = get_position_from_gauge_time(
            w3_eth.toChecksumAddress(gauge_address.lower()),
            current_period,
            point_weights_base_slot,
        )
        vote_user_slope_position = get_position_from_user_gauge(
            w3_eth.toChecksumAddress(user.lower()),
            w3_eth.toChecksumAddress(gauge_address.lower()),
            vote_user_slope_base_slot,
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

    # Proof (RLP)
    raw_proof = w3_eth.eth.get_proof(
        w3_eth.toChecksumAddress(Constants.GAUGE_CONTROLLER[protocol].lower()),
        positions,
        int(latest_header_proof["BlockNumber"]),
    )
    rlp_proof = Utils.encode_rlp_proofs(raw_proof)

    return rlp_proof


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


""" Curve case (old vyper) """


def get_position_from_user_gauge_old(user, gauge, base_slot):
    # Encode the base slot and user address, then hash
    user_encoded = keccak(encode(["uint256", "address"], [base_slot, user]))

    # Encode the result with the gauge address, then hash
    intermediate_hash = keccak(encode(["bytes32", "address"], [user_encoded, gauge]))

    # Final hash
    final_slot = keccak(encode(["bytes32"], [intermediate_hash]))

    # Convert the final hash to an integer slot number
    return int.from_bytes(final_slot, byteorder="big")


def get_position_from_gauge_time_old(gauge, time, base_slot):
    # Encode the base slot and gauge address, then hash
    gauge_encoded = keccak(encode(["uint256", "address"], [base_slot, gauge]))

    # Encode the result with the time, then hash
    intermediate_hash = keccak(encode(["bytes32", "uint256"], [gauge_encoded, time]))

    # Final hash
    final_slot = keccak(encode(["bytes32"], [intermediate_hash]))

    # Convert the final hash to an integer slot number
    return int.from_bytes(final_slot, byteorder="big")


def main():
    # Get web3 instance on Ethereum
    w3_eth = Utils.get_web3(1)

    gauge_abi = Utils.load_json("abi/GaugeController")
    platform_l2_abi = Utils.load_json("abi/PlatformL2")
    state_sender_abi = Utils.load_json("abi/StateSender")

    state_sender = Utils.load_contract(
        w3_eth, Constants.ETHEREUM_STATE_SENDER, state_sender_abi
    )
    current_period = state_sender.functions.getCurrentPeriod().call()

    protocol_data = {}

    latest_header_proof = Utils.load_json(
        f"bounties/x-chain/{current_period}/block_header"
    )

    for protocol in Constants.PROTOCOLS:
        logging.info(f"Fetching active bounties from {protocol}")

        gauge_controller = Constants.GAUGE_CONTROLLER[protocol]
        gauge_controller_contract = Utils.load_contract(
            w3_eth, gauge_controller, gauge_abi
        )

        platforms = Constants.PLATFORMS[protocol]

        protocol_data[protocol] = {}

        # Get all active bounties (on all chains / platforms of that protocol)
        active_bounties = []

        for platform_data in platforms:
            w3 = Utils.get_web3(platform_data["chainId"])
            vm = Utils.load_contract(w3, platform_data["address"], platform_l2_abi)
            bounties = Utils.get_active_bounties(vm, current_period, w3)
            # Filter out empty bounties and add chainId as a key
            active_bounties += [
                {**bounty, "chainId": platform_data["chainId"]}
                for bounty in bounties
                if bounty["bounty_id"] >= 0
                and bounty["reward_token"]
                and bounty["gauge_address"]
            ]

        all_gauges = [
            w3.toChecksumAddress(bounty["gauge_address"].lower())
            for bounty in active_bounties
        ]

        if len(all_gauges) == 0:
            logging.info(f"No active bounties found for {protocol}")
            continue

        all_voters_for_active_bounties = Utils.query_all_voters_gauges(
            gauge_controller, all_gauges
        )

        if len(all_voters_for_active_bounties) == 0:
            logging.info(f"No voters found for active bounties for {protocol}")
            continue

        active_users_for_gauges = {}

        # Now , check for each voter if he has vote (eligible for bounty) on the gauge
        for gauge_address, voters in all_voters_for_active_bounties.items():
            if not active_users_for_gauges.get(gauge_address):
                active_users_for_gauges[gauge_address] = {}
            for user in voters:
                if Utils.check_eligibility(
                    w3_eth,
                    gauge_controller_contract,
                    user,
                    gauge_address,
                    current_period,
                ):
                    logging.info(
                        f"User {user} is eligible for bounty on gauge {gauge_address}"
                    )
                    active_users_for_gauges[gauge_address][user] = {
                        "proof": ""
                    }  # Gauge -> Users -> Proof

        # Generate proofs for active gauge users
        for gauge_address, users in active_users_for_gauges.items():
            for user in users:
                proof = generate_proof(
                    w3_eth,
                    protocol,
                    gauge_address,
                    user,
                    current_period,
                    latest_header_proof,
                )
                active_users_for_gauges[gauge_address][user]["proof"] = proof.hex()

        # Add proofs for blacklist (if any) + Add user proofs per bounty ids
        for bounty in active_bounties:
            for user in active_users_for_gauges[bounty["gauge_address"]]:
                if "user_proofs" not in bounty:
                    bounty["user_proofs"] = {}
                bounty["user_proofs"][user] = active_users_for_gauges[
                    bounty["gauge_address"]
                ][user]["proof"]

            if len(bounty["blacklist"]) == 0:
                continue

            proof = ""

            blacklist_proofs = {}

            for user in bounty["blacklist"]:
                # If user / gauge is already present in active_users_for_gauges; take it
                if user in active_users_for_gauges[bounty["gauge_address"]]:
                    proof = active_users_for_gauges[bounty["gauge_address"]][user][
                        "proof"
                    ]
                else:
                    proof = generate_proof(
                        w3_eth,
                        protocol,
                        bounty["gauge_address"],
                        user,
                        current_period,
                        latest_header_proof,
                    )
                # Transform blacklist [] into {user: proof}
                blacklist_proofs[user] = proof.hex()

            # Replace "blacklist" by blacklist_proof
            bounty["blacklist"] = blacklist_proofs

        protocol_data[protocol] = active_bounties

    # Write Json files (even empty ones)
    for protocol in Constants.PROTOCOLS:
        with open(f"bounties/x-chain/{current_period}/{protocol}.json", "w") as f:
            json.dump(protocol_data[protocol], f, indent=4)


if __name__ == "__main__":
    main()
