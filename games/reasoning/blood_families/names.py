"""Names for Blood Relations people. A name tells the player the person's gender; a label (A, B, ...) does not."""

import random

from games.reasoning.family import Family, Person

MALE_NAMES = (
    "Aarav", "Adam", "Ahmed", "Aiden", "Alan", "Albert", "Amit", "Andre", "Arjun", "Arthur",
    "Ben", "Carlos", "Chen", "Daniel", "Dev", "Diego", "Dmitri", "Edward", "Elias", "Ethan",
    "Felix", "Frank", "Gabriel", "George", "Hamza", "Harry", "Hugo", "Ian", "Ivan", "Jack",
    "James", "Jason", "Kabir", "Kevin", "Kofi", "Leo", "Liam", "Lucas", "Marco", "Mark",
    "Mateo", "Nathan", "Noah", "Oliver", "Omar", "Oscar", "Pablo", "Paul", "Peter", "Rahul",
    "Raj", "Ravi", "Robert", "Ryan", "Sam", "Samir", "Simon", "Tariq", "Theo", "Victor",
    "Walter", "Yusuf", "Zane", "Hiro",
)  # fmt: skip
FEMALE_NAMES = (
    "Aisha", "Alice", "Amara", "Amy", "Anna", "Beth", "Bianca", "Carla", "Chloe", "Clara",
    "Daisy", "Diana", "Elena", "Ella", "Emma", "Eva", "Fatima", "Fiona", "Grace", "Hana",
    "Hannah", "Iris", "Isla", "Jane", "Julia", "Kavya", "Kate", "Lara", "Laura", "Leila",
    "Lily", "Lucy", "Maya", "Mei", "Mia", "Nadia", "Nina", "Nora", "Olivia", "Priya",
    "Rachel", "Rita", "Rosa", "Ruby", "Sara", "Sofia", "Sophie", "Tara", "Uma", "Vera",
    "Violet", "Yara", "Zara", "Zoe", "Anika", "Bella", "Camila", "Dana", "Esha", "Freya",
    "Gita", "Helen",
)  # fmt: skip


def rename(rng: random.Random, family: Family) -> Family:
    """The same family with each person given a name that matches their gender."""
    males, females = list(MALE_NAMES), list(FEMALE_NAMES)
    rng.shuffle(males)
    rng.shuffle(females)
    new = {p.name: (males if p.gender == "M" else females).pop() for p in family.people}
    return Family(
        [Person(new[p.name], p.gender) for p in family.people],
        {new[n]: tuple(new[p] for p in family.parents_of(n)) for n in new if family.parents_of(n)},
        [(new[a], new[b]) for a, b in family.spouse_pairs()],
    )
