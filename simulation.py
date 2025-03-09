import random
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Any
from collections import defaultdict, Counter
from itertools import combinations

class HandRank(Enum):
   HIGH_CARD = 0
   PAIR = 1
   TWO_PAIR = 2
   THREE_OF_KIND = 3
   STRAIGHT = 4
   FLUSH = 5
   FULL_HOUSE = 6
   FOUR_OF_KIND = 7
   STRAIGHT_FLUSH = 8
   ROYAL_FLUSH = 9

@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def get_value(self) -> int:
        values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                 '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        return values[self.rank]

    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit

    @staticmethod
    def value_to_rank(value: int) -> str:
        values = {2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8',
                 9: '9', 10: '10', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'}
        return values[value]

class Deck:
   def __init__(self):
       ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
       suits = ['♠', '♣', '♥', '♦']
       self.cards = [Card(rank, suit) for rank in ranks for suit in suits]

   def shuffle(self):
       random.shuffle(self.cards)

   def deal(self, n: int) -> List[Card]:
       return [self.cards.pop() for _ in range(n)]

class HandEvaluator:
    @dataclass(frozen=True)
    class HandEvaluation:
        rank: HandRank
        values: List[int]
        draws: Dict[str, float]
        blockers: List[Card]
        outs: List[Card]
        description: str

    @staticmethod
    def get_possible_hands(hole_cards: List[Card], community_cards: List[Card], blockers: Set[Card]) -> Dict[str, Any]:
        """
        Calculates all possible hands given the hole cards, community cards and blocked cards.
        """
        if not isinstance(hole_cards, list) or not isinstance(community_cards, list):
            raise ValueError("hole_cards and community_cards must be lists")
        if not isinstance(blockers, set):
            raise ValueError("blockers must be a set")

        suits_seen = defaultdict(list)
        ranks_seen = defaultdict(list)
        values_seen = defaultdict(list)

        all_known_cards = community_cards + hole_cards
        for card in all_known_cards:
            suits_seen[card.suit].append(card)
            ranks_seen[card.rank].append(card)
            values_seen[card.get_value()].append(card)

        available_cards = []
        rank_availability = defaultdict(list)  # Track by rank
        suit_availability = defaultdict(list)  # Track by suit
        value_availability = defaultdict(list) # Track by value

        for rank in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']:
            for suit in ['♠', '♣', '♥', '♦']:
                card = Card(rank, suit)
                if card not in blockers and card not in hole_cards and card not in community_cards:
                    available_cards.append(card)
                    rank_availability[rank].append(card)
                    suit_availability[suit].append(card)
                    value_availability[card.get_value()].append(card)

        possible_hands = {rank: {
            'suited': [],
            'offsuit': [],
            'pairs': [],
            'potential_draws': [],
            'blockers': [],
            'probability': 0.0,
            'hand_descriptions': []
        } for rank in HandRank}

        board_ranks = Counter(card.rank for card in community_cards)
        board_suits = Counter(card.suit for card in community_cards)
        board_values = sorted([card.get_value() for card in community_cards])
        board_high = max(board_values) if board_values else 0
        board_low = min(board_values) if board_values else 0

        board_texture = {
            'paired': bool(any(count >= 2 for count in board_ranks.values())),
            'trips': bool(any(count >= 3 for count in board_ranks.values())),
            'suited': bool(any(count >= 3 for count in board_suits.values())),
            'rainbow': len(board_suits) >= 3 if community_cards else False,
            'connected': bool(any(board_values[i] - board_values[i+1] == 1
                                for i in range(len(board_values)-1))),
            'gaps': [board_values[i] - board_values[i+1]
                    for i in range(len(board_values)-1)] if len(board_values) > 1 else [],
            'high_card': board_high,
            'low_card': board_low,
            'dynamic_ranges': []
        }

        best_rank = HandRank.HIGH_CARD
        all_values = sorted({c.get_value() for c in all_known_cards})
        suits = ['♠', '♣', '♥', '♦']

        for suit in suits:
            suited_cards = [c for c in all_known_cards if c.suit == suit]
            suited_values = sorted({c.get_value() for c in suited_cards})
            available_suited = [c for c in available_cards if c.suit == suit]

            if len(suited_cards) + len(available_suited) >= 5:
                royal_values = {10, 11, 12, 13, 14}
                missing_royal = royal_values - {c.get_value() for c in suited_cards}
                available_royal = {c.get_value() for c in available_suited} & missing_royal

                if len(missing_royal) <= len(available_suited) and missing_royal.issubset(available_royal):
                    best_rank = HandRank.ROYAL_FLUSH
                    break

                all_possible_values = sorted(list({c.get_value() for c in suited_cards} |
                                                {c.get_value() for c in available_suited}))

                straight_windows = []
                for i in range(len(all_possible_values) - 4):
                    window = all_possible_values[i:i+5]
                    if window[-1] - window[0] == 4:
                        straight_windows.append(window)

                if 14 in all_possible_values and all(x in all_possible_values for x in [2,3,4,5]):
                    straight_windows.append([14,5,4,3,2])

                if straight_windows:
                    best_rank = HandRank(max(best_rank.value, HandRank.STRAIGHT_FLUSH.value))

        for value, cards in ranks_seen.items():
            if len(cards) == 4:
                best_rank = HandRank(max(best_rank.value, HandRank.FOUR_OF_KIND.value))
                break
            elif len(cards) + len(value_availability[value]) >= 4:
                best_rank = HandRank(max(best_rank.value, HandRank.FOUR_OF_KIND.value))
                break

        trips_values = [value for value, cards in ranks_seen.items() if len(cards) >= 3]
        pairs_values = [value for value, cards in ranks_seen.items() if len(cards) >= 2]

        if len(trips_values) >= 2 or (len(trips_values) >= 1 and len(pairs_values) >= 1):
            best_rank = HandRank(max(best_rank.value, HandRank.FULL_HOUSE.value))
        else:
            for value, seen_cards in ranks_seen.items():
                avail = len(value_availability[value])
                if len(seen_cards) + avail >= 3:
                    for pair_value, pair_cards in ranks_seen.items():
                        if pair_value != value:
                            pair_avail = len(value_availability[pair_value])
                            if len(pair_cards) + pair_avail >= 2:
                                best_rank = HandRank(max(best_rank.value, HandRank.FULL_HOUSE.value))
                                break

        for suit, cards in suits_seen.items():
            if len(cards) + len(suit_availability[suit]) >= 5:
                best_rank = HandRank(max(best_rank.value, HandRank.FLUSH.value))
                break

        all_possible_values = sorted(list({c.get_value() for c in all_known_cards} |
                                        {c.get_value() for c in available_cards}))

        for i in range(len(all_possible_values) - 4):
            window = all_possible_values[i:i+5]
            if window[-1] - window[0] == 4:
                best_rank = HandRank(max(best_rank.value, HandRank.STRAIGHT.value))
                break

        if 14 in all_possible_values and all(x in all_possible_values for x in [2,3,4,5]):
            best_rank = HandRank(max(best_rank.value, HandRank.STRAIGHT.value))

        for value, cards in ranks_seen.items():
            if len(cards) >= 3 or len(cards) + len(value_availability[value]) >= 3:
                best_rank = HandRank(max(best_rank.value, HandRank.THREE_OF_KIND.value))
                break

        pairs_count = len([v for v, cards in ranks_seen.items() if len(cards) >= 2])
        if pairs_count >= 2:
            best_rank = HandRank(max(best_rank.value, HandRank.TWO_PAIR.value))
        else:
            potential_pairs = 0
            for value, cards in ranks_seen.items():
                if len(cards) + len(value_availability[value]) >= 2:
                    potential_pairs += 1
                    if potential_pairs >= 2:
                        best_rank = HandRank(max(best_rank.value, HandRank.TWO_PAIR.value))
                        break

        for value, cards in ranks_seen.items():
            if len(cards) >= 2 or len(cards) + len(value_availability[value]) >= 2:
                best_rank = HandRank(max(best_rank.value, HandRank.PAIR.value))
                break

        for card1, card2 in combinations(available_cards, 2):
            test_hand = HandEvaluator.evaluate_hand([card1, card2] + community_cards)

            if card1.suit == card2.suit:
                category = 'suited'
                desc = f"{card1.rank}{card2.rank}s"
            elif card1.rank == card2.rank:
                category = 'pairs'
                desc = f"Pocket {card1.rank}s"
            else:
                category = 'offsuit'
                desc = f"{max(card1.rank, card2.rank)}{min(card1.rank, card2.rank)}o"

            possible_hands[test_hand.rank][category].append((card1, card2))
            possible_hands[test_hand.rank]['hand_descriptions'].append(desc)

            if test_hand.rank.value > best_rank.value:
                possible_hands[test_hand.rank]['blockers'].extend([card1, card2])

        total_combos = sum(
            len(hands[category])
            for rank in possible_hands
            for category in ['suited', 'offsuit', 'pairs']
            for hands in [possible_hands[rank]]
        )

        for rank in HandRank:
            total_hands = sum(len(possible_hands[rank][cat])
                            for cat in ['suited', 'offsuit', 'pairs'])
            if total_combos > 0:
                possible_hands[rank]['probability'] = total_hands / total_combos

            for category in ['suited', 'offsuit', 'pairs']:
                if possible_hands[rank][category]:
                    possible_hands[rank][category].sort(
                        key=lambda x: (
                            max(c.get_value() for c in x),
                            min(c.get_value() for c in x)
                        ),
                        reverse=True
                    )

            possible_hands[rank]['blockers'] = list(set(possible_hands[rank]['blockers']))

        return {
            'hands': possible_hands,
            'statistics': {
                'total_combinations': total_combos,
                'best_possible': best_rank,
                'board_texture': board_texture,
                'available_cards': len(available_cards),
                'rank_availability': {r: len(cards) for r, cards in rank_availability.items()},
                'suit_availability': {s: len(cards) for s, cards in suit_availability.items()}
            }
        }

    @staticmethod
    def evaluate_draws(community: List[Card], blockers: Set[Card]) -> Dict[str, float]:

        draws = {}

        if len(community) >= 5:
            return draws

        suit_count = Counter(card.suit for card in community)
        values = sorted([card.get_value() for card in community])

        cards_to_come = 5 - len(community)
        remaining_deck = 52 - len(blockers) - len(community)
        if remaining_deck <= 0:
            return draws

        outs_multiplier = 100 / remaining_deck

        for suit, count in suit_count.items():
            remaining_suit = sum(1 for r in ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
                            for s in [suit]
                            if Card(r,s) not in blockers and Card(r,s) not in community)

            if count == 4:
                if remaining_suit > 0:
                    equity = (remaining_suit / remaining_deck) * 100
                    draws['Flush Draw'] = equity
            elif count == 3:
                if remaining_suit >= 2:
                    if cards_to_come == 2:
                        probability = (remaining_suit / cards_to_come) * ((remaining_suit - 1) / (cards_to_come - 1))
                        draws['Backdoor Flush Draw'] = probability * 100
                    else:
                        draws['Potential Flush Draw'] = (remaining_suit / remaining_deck) * 100

        if len(values) >= 2:
            all_values = set(values)
            min_straight_start = max(min(values) - 4, 2)
            max_straight_start = min(max(values), 10)

            ace_present = 14 in all_values
            wheel_values = {2, 3, 4, 5}
            wheel_missing = wheel_values - all_values

            if ace_present and len(wheel_missing) <= 2:
                available_wheel_outs = sum(1 for v in wheel_missing
                                        for suit in ['♠','♣','♥','♦']
                                        if Card(Card.value_to_rank(v), suit) not in blockers
                                        and Card(Card.value_to_rank(v), suit) not in community)
                if available_wheel_outs > 0:
                    if len(wheel_missing) == 1:
                        draws['Open-Ended Wheel Draw'] = available_wheel_outs * outs_multiplier
                    else:
                        draws['Wheel Gutshot Draw'] = available_wheel_outs * outs_multiplier

            for i in range(min_straight_start - 1, max_straight_start + 2):
                window = set(range(i, i + 5))
                missing = window - all_values

                wrap_values = set(range(i-1, i+6))
                wrap_missing = wrap_values - all_values

                if len(missing) == 1:
                    available_outs = sum(1 for v in missing
                                    for suit in ['♠','♣','♥','♦']
                                    if Card(Card.value_to_rank(v), suit) not in blockers
                                    and Card(Card.value_to_rank(v), suit) not in community)
                    if available_outs > 0:
                        if min(missing) == i or max(missing) == i + 4:
                            draws['Open-Ended Straight Draw'] = max(
                                draws.get('Open-Ended Straight Draw', 0),
                                available_outs * outs_multiplier
                            )
                        else:
                            draws['Gutshot Straight Draw'] = max(
                                draws.get('Gutshot Straight Draw', 0),
                                available_outs * outs_multiplier
                            )

                elif len(wrap_missing) == 2 and len(wrap_values & all_values) >= 4:
                    available_wrap_outs = sum(1 for v in wrap_missing
                                        for suit in ['♠','♣','♥','♦']
                                        if Card(Card.value_to_rank(v), suit) not in blockers
                                        and Card(Card.value_to_rank(v), suit) not in community)
                    if available_wrap_outs > 0:
                        draws['Wrap-Around Straight Draw'] = available_wrap_outs * outs_multiplier

                elif len(missing) == 2:
                    available_outs = sum(1 for v in missing
                                    for suit in ['♠','♣','♥','♦']
                                    if Card(Card.value_to_rank(v), suit) not in blockers
                                    and Card(Card.value_to_rank(v), suit) not in community)
                    if available_outs >= 2:
                        if cards_to_come == 2:
                            probability = (available_outs / remaining_deck) * ((available_outs - 4) / (remaining_deck - 1))
                            draws['Backdoor Straight Draw'] = max(
                                draws.get('Backdoor Straight Draw', 0),
                                probability * 100
                            )
                        else:
                            draws['Potential Straight Draw'] = available_outs * outs_multiplier

            if len(values) >= 3:
                for i in range(min_straight_start, max_straight_start + 1):
                    window = set(range(i, i + 6))
                    missing = window - all_values
                    if len(missing) == 2 and len(window & all_values) >= 4:
                        available_outs = sum(1 for v in missing
                                        for suit in ['♠','♣','♥','♦']
                                        if Card(Card.value_to_rank(v), suit) not in blockers
                                        and Card(Card.value_to_rank(v), suit) not in community)
                        if available_outs > 0:
                            draws['Double Gutshot Draw'] = available_outs * outs_multiplier

        flush_draw = 'Flush Draw' in draws
        straight_draws = {k: v for k, v in draws.items() if 'Straight' in k and 'Backdoor' not in k}

        if flush_draw and straight_draws:
            flush_equity = draws.get('Flush Draw', 0)
            straight_equity = sum(straight_draws.values())

            overlap_adjustment = 0.2 * min(flush_equity, straight_equity)
            combo_equity = flush_equity + straight_equity - overlap_adjustment

            draws['Combination Draw'] = combo_equity

            for straight_type in straight_draws:
                draws[f'Flush + {straight_type}'] = combo_equity

        if len(community) == 3:
            board_high = max(values)
            overcard_outs = sum(1 for r in ['A','K','Q','J']
                            for s in ['♠','♣','♥','♦']
                            if Card(r,s) not in blockers
                            and Card(r,s) not in community
                            and Card(r,s).get_value() > board_high)
            if overcard_outs > 0:
                draws['Overcard Draw'] = overcard_outs * outs_multiplier

                high_overcard_outs = sum(1 for r in ['A','K']
                                    for s in ['♠','♣','♥','♦']
                                    if Card(r,s) not in blockers
                                    and Card(r,s) not in community)
                if high_overcard_outs >= 2:
                    draws['Double Overcard Draw'] = high_overcard_outs * outs_multiplier

        return draws

    @staticmethod
    def has_straight_potential(cards: List[Card]) -> bool:

        if len(cards) < 3:
            return False

        values = sorted(set(card.get_value() for card in cards))
        for i in range(len(values) - 2):
            if values[i+2] - values[i] <= 4:
                return True
        return False

    @staticmethod
    def evaluate_hand(cards: List[Card]) -> HandEvaluation:
        if not cards:
            return HandEvaluator.HandEvaluation(
                rank=HandRank.HIGH_CARD,
                values=[],
                draws={},
                blockers=[],
                outs=[],
                description="Empty hand"  # Improved empty hand description
            )

        if len(cards) == 2:
            card1, card2 = sorted(cards, key=lambda x: x.get_value(), reverse=True)
            suited = card1.suit == card2.suit
            pair = card1.rank == card2.rank

            if pair:
                desc = f"Pocket {Card.value_to_rank(card1.get_value())}s"
                rank = HandRank.PAIR
                values = [card1.get_value(), card2.get_value()]
            else:
                suited_str = "suited" if suited else "offsuit"
                desc = f"{Card.value_to_rank(card1.get_value())}-{Card.value_to_rank(card2.get_value())} {suited_str}"
                rank = HandRank.HIGH_CARD
                values = [card1.get_value(), card2.get_value()]

            return HandEvaluator.HandEvaluation(
                rank=rank,
                values=values,
                draws={},
                blockers=cards,
                outs=[],
                description=desc
            )

        sorted_cards = sorted(cards, key=lambda x: x.get_value(), reverse=True)

        suits = defaultdict(list)
        ranks = defaultdict(list)
        values = []
        value_set = set()

        for card in sorted_cards:
            suits[card.suit].append(card)
            ranks[card.get_value()].append(card)
            if card.get_value() not in value_set:
                values.append(card.get_value())
                value_set.add(card.get_value())

        for suit, suit_cards in suits.items():
            if len(suit_cards) >= 5:
                suited_values = sorted([c.get_value() for c in suit_cards], reverse=True)

                if suited_values[:5] == [14, 13, 12, 11, 10]:
                    return HandEvaluator.HandEvaluation(
                        rank=HandRank.ROYAL_FLUSH,
                        values=[14],
                        draws={},
                        blockers=suit_cards[:5],
                        outs=[],
                        description="Royal Flush"
                    )

                straight_values = []
                for i in range(len(suited_values) - 4):
                    window = suited_values[i:i+5]
                    if window[-1] == window[0] - 4:
                        straight_values = window
                        break

                if not straight_values and 14 in suited_values:
                    wheel_values = [14, 5, 4, 3, 2]
                    if all(v in suited_values for v in wheel_values):
                        wheel_cards = [c for c in suit_cards if c.get_value() in wheel_values]
                        return HandEvaluator.HandEvaluation(
                            rank=HandRank.STRAIGHT_FLUSH,
                            values=[5, 4, 3, 2, 1],  # Standardized wheel values
                            draws={},
                            blockers=wheel_cards,
                            outs=[],
                            description="Straight Flush, Five High (Wheel)"
                        )

                if straight_values:
                    straight_cards = [c for c in suit_cards if c.get_value() in straight_values]
                    return HandEvaluator.HandEvaluation(
                        rank=HandRank.STRAIGHT_FLUSH,
                        values=straight_values,
                        draws={},
                        blockers=straight_cards,
                        outs=[],
                        description=f"Straight Flush, {Card.value_to_rank(straight_values[0])} high"
                    )

        for value, cards_of_rank in ranks.items():
            if len(cards_of_rank) == 4:
                kicker_candidates = [v for v in values if v != value]
                kicker = max(kicker_candidates) if kicker_candidates else value
                kicker_card = next(c for c in sorted_cards if c.get_value() == kicker and c not in cards_of_rank)
                return HandEvaluator.HandEvaluation(
                    rank=HandRank.FOUR_OF_KIND,
                    values=[value, kicker],
                    draws={},
                    blockers=cards_of_rank + [kicker_card],
                    outs=[],
                    description=f"Four of a Kind, {Card.value_to_rank(value)}s with {Card.value_to_rank(kicker)} kicker"
                )

        trips = sorted([v for v, cards in ranks.items() if len(cards) >= 3], reverse=True)
        pairs = sorted([v for v, cards in ranks.items() if len(cards) >= 2], reverse=True)

        if trips:
            if len(trips) > 1:
                return HandEvaluator.HandEvaluation(
                    rank=HandRank.FULL_HOUSE,
                    values=[trips[0], trips[1]],
                    draws={},
                    blockers=[c for v in trips[:2] for c in ranks[v]],
                    outs=[],
                    description=f"Full House, {Card.value_to_rank(trips[0])}s full of {Card.value_to_rank(trips[1])}s"
                )
            pairs_without_trips = [p for p in pairs if p != trips[0]]
            if pairs_without_trips:
                return HandEvaluator.HandEvaluation(
                    rank=HandRank.FULL_HOUSE,
                    values=[trips[0], pairs_without_trips[0]],
                    draws={},
                    blockers=[c for v in [trips[0], pairs_without_trips[0]] for c in ranks[v]],
                    outs=[],
                    description=f"Full House, {Card.value_to_rank(trips[0])}s full of {Card.value_to_rank(pairs_without_trips[0])}s"
                )

        for suit, suit_cards in suits.items():
            if len(suit_cards) >= 5:
                top_five = sorted(suit_cards, key=lambda x: x.get_value(), reverse=True)[:5]
                values = [c.get_value() for c in top_five]
                return HandEvaluator.HandEvaluation(
                    rank=HandRank.FLUSH,
                    values=values,
                    draws={},
                    blockers=top_five,
                    outs=[],
                    description=f"Flush, {Card.value_to_rank(values[0])} high"
                )

        straight_values = []

        for i in range(len(values) - 4):
            window = values[i:i+5]
            if window[-1] == window[0] - 4:
                straight_values = window
                break

        if not straight_values and 14 in values:
            wheel_values = [5, 4, 3, 2, 1]  # Standardized wheel values
            if all(v in values or (v == 1 and 14 in values) for v in wheel_values):
                straight_cards = []
                for value in [5, 4, 3, 2]:
                    straight_cards.extend(c for c in sorted_cards if c.get_value() == value)
                straight_cards.extend(c for c in sorted_cards if c.get_value() == 14)  # Add ace
                return HandEvaluator.HandEvaluation(
                    rank=HandRank.STRAIGHT,
                    values=wheel_values,
                    draws={},
                    blockers=straight_cards[:5],
                    outs=[],
                    description="Straight, Five High (Wheel)"
                )

        if straight_values:
            straight_cards = []
            for value in straight_values:
                straight_cards.extend(c for c in sorted_cards if c.get_value() == value)
            return HandEvaluator.HandEvaluation(
                rank=HandRank.STRAIGHT,
                values=straight_values,
                draws={},
                blockers=straight_cards[:5],
                outs=[],
                description=f"Straight, {Card.value_to_rank(straight_values[0])} high"
            )

        if trips:
            kickers = [v for v in values if v != trips[0]][:2]  # Get up to 2 kickers
            kicker_cards = [c for c in sorted_cards if c.get_value() in kickers and c not in ranks[trips[0]]][:2]

            if len(kickers) >= 2:
                kicker_desc = f"with {Card.value_to_rank(kickers[0])}, {Card.value_to_rank(kickers[1])} kickers"
            elif len(kickers) == 1:
                kicker_desc = f"with {Card.value_to_rank(kickers[0])} kicker"
            else:
                kicker_desc = ""

            return HandEvaluator.HandEvaluation(
                rank=HandRank.THREE_OF_KIND,
                values=[trips[0]] + kickers,
                draws={},
                blockers=ranks[trips[0]] + kicker_cards,
                outs=[],
                description=f"Three of a Kind, {Card.value_to_rank(trips[0])}s {kicker_desc}".strip()
            )

        if len(pairs) >= 2:
            kickers = [v for v in values if v not in pairs[:2]]
            kicker = kickers[0] if kickers else pairs[2] if len(pairs) > 2 else pairs[1]
            kicker_card = next((c for c in sorted_cards if c.get_value() == kicker and c not in ranks[pairs[0]] and c not in ranks[pairs[1]]), None)
            return HandEvaluator.HandEvaluation(
                rank=HandRank.TWO_PAIR,
                values=pairs[:2] + [kicker],
                draws={},
                blockers=[c for v in pairs[:2] for c in ranks[v]] + ([kicker_card] if kicker_card else []),
                outs=[],
                description=f"Two Pair, {Card.value_to_rank(pairs[0])}s and {Card.value_to_rank(pairs[1])}s with {Card.value_to_rank(kicker)} kicker"
            )

        if pairs:
            kickers = [v for v in values if v != pairs[0]][:3]
            kicker_cards = [c for c in sorted_cards if c.get_value() in kickers and c not in ranks[pairs[0]]][:3]
            return HandEvaluator.HandEvaluation(
                rank=HandRank.PAIR,
                values=[pairs[0]] + kickers,
                draws={},
                blockers=ranks[pairs[0]] + kicker_cards,
                outs=[],
                description=f"Pair of {Card.value_to_rank(pairs[0])}s with {', '.join(Card.value_to_rank(k) for k in kickers)} kicker{'s' if len(kickers) > 1 else ''}"
            )

        high_cards = sorted_cards[:5]
        values_list = [c.get_value() for c in high_cards]
        return HandEvaluator.HandEvaluation(
            rank=HandRank.HIGH_CARD,
            values=values_list,
            draws={},
            blockers=high_cards,
            outs=[],
            description=f"High Card, {Card.value_to_rank(values_list[0])} with {', '.join(Card.value_to_rank(v) for v in values_list[1:])} kicker{'s' if len(values_list) > 2 else ''}"
        )

    @staticmethod
    def detect_straights(values: List[int]) -> List[List[int]]:
        """Helper method to detect straight patterns."""
        patterns = []
        for i in range(len(values) - 3):
            window = values[i:i+5]
            gaps = sum(window[j] - window[j+1] - 1 for j in range(len(window)-1) if j+1 < len(window))
            if gaps == 0:
                patterns.append(window)
            elif gaps == 1 and len(window) >= 4:
                patterns.append(window)
        return patterns

    @staticmethod
    def get_straight_draws(pattern: List[int], num_cards: int) -> Dict[str, float]:
        """Helper method to calculate straight draw probabilities."""
        draws = {}
        if len(pattern) == 4:
            if pattern[0] - pattern[-1] == 4:  # Open-ended
                draws['Open-Ended Straight Draw'] = 8 / (47 - num_cards)
            else:  # Gutshot
                draws['Gutshot Straight Draw'] = 4 / (47 - num_cards)
        return draws

    @staticmethod
    def evaluate_made_hand(cards: List[Card], flush_cards: List[Card], straight_patterns: List[List[int]],
                          rank_groups: Dict[int, List[Card]]) -> Tuple[HandRank, List[int]]:
        if flush_cards:
            flush_values = [c.get_value() for c in flush_cards]

            if set(flush_values) == {14, 13, 12, 11, 10}:
                return (HandRank.ROYAL_FLUSH, [14])

            for pattern in straight_patterns:
                if set(pattern).issubset(set(flush_values)):
                    return (HandRank.STRAIGHT_FLUSH, [max(pattern)])

        for value, cards_of_rank in rank_groups.items():
            if len(cards_of_rank) == 4:
                kicker = max(v for v in rank_groups.keys() if v != value)
                return (HandRank.FOUR_OF_KIND, [value, kicker])

        trips = [v for v, cards in rank_groups.items() if len(cards) == 3]
        pairs = [v for v, cards in rank_groups.items() if len(cards) == 2]

        if trips and (len(trips) > 1 or pairs):
            trips.sort(reverse=True)
            if len(trips) > 1:
                return (HandRank.FULL_HOUSE, [trips[0], trips[1]])
            else:
                return (HandRank.FULL_HOUSE, [trips[0], max(pairs)])

        if flush_cards:
            return (HandRank.FLUSH, [c.get_value() for c in flush_cards])

        if straight_patterns:
            return (HandRank.STRAIGHT, [max(pattern) for pattern in straight_patterns])

        if trips:
            kickers = sorted([v for v in rank_groups.keys() if v != trips[0]], reverse=True)[:2]
            return (HandRank.THREE_OF_KIND, [trips[0]] + kickers)

        if len(pairs) >= 2:
            pairs.sort(reverse=True)
            kicker = max(v for v in rank_groups.keys() if v not in pairs[:2])
            return (HandRank.TWO_PAIR, pairs[:2] + [kicker])

        if pairs:
            kickers = sorted([v for v in rank_groups.keys() if v != pairs[0]], reverse=True)[:3]
            return (HandRank.PAIR, [pairs[0]] + kickers)

        return (HandRank.HIGH_CARD, sorted([c.get_value() for c in cards], reverse=True)[:5])

    @staticmethod
    def calculate_blockers(made_hand: Tuple[HandRank, List[int]], cards: List[Card]) -> List[Card]:
        blockers = set()
        hand_rank = made_hand[0]
        hand_values = made_hand[1]

        if hand_rank == HandRank.FLUSH:
            flush_suit = next(card.suit for card in cards if card.get_value() == hand_values[0])
            blockers.update(card for card in cards if card.suit == flush_suit)

        elif hand_rank == HandRank.STRAIGHT:
            straight_high = hand_values[0]
            for card in cards:
                if card.get_value() > straight_high:blockers.add(card)

        elif hand_rank in {HandRank.THREE_OF_KIND, HandRank.FOUR_OF_KIND}:
            blockers.update(card for card in cards if card.get_value() == hand_values[0])

        return list(blockers)

    @staticmethod
    def generate_hand_description(made_hand: Tuple[HandRank, List[int]],
                                draws: Dict[str, float],
                                outs: Set[Card]) -> str:
        hand_rank = made_hand[0]
        hand_values = made_hand[1]

        value_names = {14: 'Ace', 13: 'King', 12: 'Queen', 11: 'Jack'}
        def get_value_name(val):
            return value_names.get(val, str(val))

        desc = [f"{hand_rank.name.replace('_', ' ').title()}"]

        if hand_rank == HandRank.HIGH_CARD:
            desc.append(f"with {get_value_name(hand_values[0])} high")
        elif hand_rank == HandRank.PAIR:
            desc.append(f"of {get_value_name(hand_values[0])}s")
        elif hand_rank == HandRank.TWO_PAIR:
            desc.append(f"with {get_value_name(hand_values[0])}s and {get_value_name(hand_values[1])}s")
        elif hand_rank == HandRank.THREE_OF_KIND:
            desc.append(f"with three {get_value_name(hand_values[0])}s")

        if draws:
            desc.append("\nDrawing to:")
            for draw_type, equity in draws.items():
                desc.append(f"- {draw_type} ({equity:.1%} equity)")

        if outs:
            desc.append(f"\n{len(outs)} outs to improve")

        return ' '.join(desc)






def simulate_single_round(args):
    hole_cards, community_cards, available_cards, num_players, unknown_cards = args

    if not community_cards:
        hero_hand = sorted(hole_cards, key=lambda x: x.get_value(), reverse=True)
        hero_suited = hero_hand[0].suit == hero_hand[1].suit
        hero_paired = hero_hand[0].rank == hero_hand[1].rank
        hero_values = [c.get_value() for c in hero_hand]

        simulation_deck = list(available_cards)  # Create a new list instead of using .copy()
        random.shuffle(simulation_deck)
        community = []
        for _ in range(5):
            if simulation_deck:
                community.append(simulation_deck.pop())
        hero_best = HandEvaluator.evaluate_hand(hole_cards + community)
        for _ in range(num_players - 1):
            if len(simulation_deck) < 2:
                break
            villain_hole = [simulation_deck.pop(), simulation_deck.pop()]
            villain_best = HandEvaluator.evaluate_hand(villain_hole + community)
            if villain_best.rank.value > hero_best.rank.value:
                return "lose"
            elif villain_best.rank.value == hero_best.rank.value:
                if hero_best.rank == HandRank.STRAIGHT:
                    hero_high = max(hero_best.values)
                    villain_high = max(villain_best.values)
                    if villain_high > hero_high:
                        return "lose"
                    elif villain_high == hero_high:
                        return "tie"
                else:
                    for hero_val, villain_val in zip(hero_best.values, villain_best.values):
                        if villain_val > hero_val:
                            return "lose"
                        elif villain_val < hero_val:
                            break
                    else:
                        return "tie"
        return "win"
    simulation_deck = list(available_cards)
    random.shuffle(simulation_deck)
    board = list(community_cards)
    if unknown_cards > 0:
        board.extend(simulation_deck[:unknown_cards])
        simulation_deck = simulation_deck[unknown_cards:]
    hero_best = HandEvaluator.evaluate_hand(hole_cards + board)
    for _ in range(num_players - 1):
        if len(simulation_deck) < 2:
            break
        villain_hole = [simulation_deck.pop(), simulation_deck.pop()]
        villain_best = HandEvaluator.evaluate_hand(villain_hole + board)
        if villain_best.rank.value > hero_best.rank.value:
            return "lose"
        elif villain_best.rank.value == hero_best.rank.value:
            if hero_best.rank == HandRank.STRAIGHT:
                hero_high = max(hero_best.values)
                villain_high = max(villain_best.values)
                if villain_high > hero_high:
                    return "lose"
                elif villain_high == hero_high:
                    return "tie"
            else:
                for hero_val, villain_val in zip(hero_best.values, villain_best.values):
                    if villain_val > hero_val:
                        return "lose"
                    elif villain_val < hero_val:
                        break
                else:  # All values equal
                    return "tie"
    return "win"