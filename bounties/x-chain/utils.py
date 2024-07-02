import os, json, rlp
import requests
from dotenv import load_dotenv
from web3 import Web3
from w3multicall.multicall import W3Multicall
from hexbytes import HexBytes

load_dotenv()


class Constants:
    ETHEREUM_STATE_SENDER = "0x189B2c0e4e8e221173f266f311C949498A4859D1"
    MAINNET_URL = "https://eth-mainnet.g.alchemy.com/v2/" + os.getenv("ALCHEMY_API_KEY")
    ARBITRUM_URL = "https://arb1.arbitrum.io/rpc"
    OPTIMISM_URL = "https://optimism.llamarpc.com"
    BASE_URL = "https://base.llamarpc.com"
    POLYGON_URL = "https://polygon.llamarpc.com"

    AGNOSTIC_ENDPOINT = os.getenv("AGNOSTIC_ENDPOINT")
    AGNOSTIC_HEADERS = {
        "Authorization": os.getenv("AGNOSTIC_API_KEY"),
        "Cache-Control": "max-age=300",
    }
    PROTOCOLS = ["curve", "balancer", "frax", "fxn"]

    # To get positions
    GAUGES_SLOTS = {
        "curve": {
            "vote_user_slope": 9,
            "last_user_vote": 11,
            "point_weights": 12,
        },
        "balancer": {
            "vote_user_slope": 1000000005,
            "last_user_vote": 1000000007,
            "point_weights": 1000000008,
        },
        "frax": {
            "vote_user_slope": 1000000008,
            "last_user_vote": 1000000010,
            "point_weights": 10000000011,
        },
        "fxn": {
            "vote_user_slope": 1000000008,
            "last_user_vote": 1000000010,
            "point_weights": 10000000011,
        },
    }

    PLATFORMS = {
        "curve": [
            {
                "chainId": 42161,
                "address": "0xB854cF650F5492d23e52cb2A7a58B787fC25B0Bb",
            }
        ],
        "balancer": [
            {
                "chainId": 42161,
                "address": "0xFf276AB161f48f6DBa99dE4601f9a518D1d903f9",
            }
        ],
        "frax": [
            {
                "chainId": 42161,
                "address": "0x4941c004dC4Ae7bcb74B404fbd4ff07Dc32e3ecc",
            }
        ],
        "fxn": [
            {
                "chainId": 42161,
                "address": "0xE5cE02443942B006d0851d6e73d9dbEeE743b88d",
            }
        ],
    }

    GAUGE_CONTROLLER = {
        "curve": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "balancer": "0xC128468b7Ce63eA702C1f104D55A2566b13D3ABD",
        "frax": "0x3669C421b77340B2979d1A00a792CC2ee0FcE737",
        "fxn": "0xe60eB8098B34eD775ac44B1ddE864e098C6d7f37",
    }

    """ Types """

    ActiveBountyType = {
        "bounty_id": "",
        "reward_token": "",
        "gauge_address": "",
        "blacklist": [],
    }


class Utils:
    @staticmethod
    def get_web3(chainId):
        if chainId == 1:
            return Web3(Web3.HTTPProvider(Constants.MAINNET_URL))
        elif chainId == 42161:
            return Web3(Web3.HTTPProvider(Constants.ARBITRUM_URL))
        elif chainId == 10:
            return Web3(Web3.HTTPProvider(Constants.OPTIMISM_URL))
        elif chainId == 137:
            return Web3(Web3.HTTPProvider(Constants.POLYGON_URL))
        elif chainId == 8453:
            return Web3(Web3.HTTPProvider(Constants.BASE_URL))
        else:
            raise Exception("ChainId not supported")

    @staticmethod
    def load_json(name):
        with open(name + ".json", "r") as f:
            return json.load(f)

    @staticmethod
    def load_contract(w3, address, abi):
        return w3.eth.contract(
            address=Web3.toChecksumAddress(address),
            abi=abi,
        )

    @staticmethod
    def encode_rlp_proofs(proofs):
        account_proof = list(map(rlp.decode, map(HexBytes, proofs["accountProof"])))
        storage_proofs = [
            list(map(rlp.decode, map(HexBytes, proof["proof"])))
            for proof in proofs["storageProof"]
        ]
        return rlp.encode([account_proof, *storage_proofs])

    @staticmethod
    def get_event_logs(
        w3, contract_address, abi, event_name, from_block, to_block, filters=None
    ):
        contract_address = Web3.toChecksumAddress(contract_address.lower())
        contract = w3.eth.contract(address=contract_address, abi=Utils.load_json(abi))
        return getattr(contract.events, event_name).getLogs(
            fromBlock=from_block, toBlock=to_block, argument_filters=filters
        )

    """ Votemarket platform """

    @staticmethod
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
                    vm.address,
                    "getBlacklistedAddressesPerBounty(uint256)(address[])",
                    [i],
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
                        "bounty_id": i,
                        "reward_token": bounty_details[2],
                        "gauge_address": bounty_details[0],
                        "blacklist": blacklist,
                    }
                )
        return active_bounties

    @staticmethod
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
            Constants.AGNOSTIC_ENDPOINT, headers=Constants.AGNOSTIC_HEADERS, data=query
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

    @staticmethod
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
            w3.toChecksumAddress(user.lower()),
            w3.toChecksumAddress(gauge_address.lower()),
        ).call()
        (slope, power, end) = gauge_controller.functions.vote_user_slopes(
            w3.toChecksumAddress(user.lower()),
            w3.toChecksumAddress(gauge_address.lower()),
        ).call()

        if slope != 0 and current_period < end and current_period > last_vote:
            is_eligible = True

        return is_eligible
