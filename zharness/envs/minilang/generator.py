"""Generate deterministic MiniLang hidden-rule worlds and labeled tasks."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Dict, List, Optional, Sequence, Tuple


ACTIONS = ("jump", "walk", "spin", "lift")
OBJECTS = ("crystal", "door", "lamp", "orb")
COLORS = ("red", "blue", "green")
COUNTS = (1, 2, 3)
SLOTS = ("neg", "count", "color", "object", "action")
ORDERS = (
    ("neg", "count", "color", "object", "action"),
    ("action", "object", "color", "count", "neg"),
    ("color", "object", "action", "neg", "count"),
    ("count", "action", "color", "object", "neg"),
)
VOCAB = (
    "dak",
    "mip",
    "zor",
    "fen",
    "luz",
    "pav",
    "ket",
    "nuv",
    "sai",
    "rom",
    "vek",
    "tul",
    "bex",
    "qir",
    "hano",
    "wop",
    "grel",
    "soma",
    "nari",
    "zel",
    "tavo",
    "riku",
    "mora",
    "lafi",
)


@dataclass(frozen=True)
class Meaning:
    action: str
    object: str
    color: str
    count: int
    neg: bool = False

    def concept_ids(self) -> Tuple[str, ...]:
        concepts = (
            f"action:{self.action}",
            f"object:{self.object}",
            f"color:{self.color}",
            f"count:{self.count}",
        )
        if self.neg:
            return concepts + ("neg:true",)
        return concepts

    def to_dict(self) -> Dict[str, object]:
        return {
            "action": self.action,
            "object": self.object,
            "color": self.color,
            "count": self.count,
            "neg": self.neg,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, object]) -> "Meaning":
        return cls(
            action=str(value.get("action", "")),
            object=str(value.get("object", "")),
            color=str(value.get("color", "")),
            count=int(value.get("count", 0)),
            neg=bool(value.get("neg", False)),
        )


@dataclass(frozen=True)
class Example:
    command: str
    meaning: Meaning

    def to_prompt(self) -> str:
        return f"{self.command} => {self.meaning.to_dict()}"


@dataclass(frozen=True)
class Task:
    task_id: str
    kind: str
    command: Optional[str]
    meaning: Optional[Meaning]

    def to_prompt(self) -> str:
        if self.kind == "parse":
            return f'{self.task_id}: parse command "{self.command}" into meaning JSON'
        if self.kind == "generate" and self.meaning is not None:
            return f"{self.task_id}: generate the MiniLang command for {self.meaning.to_dict()}"
        raise ValueError(f"unknown task kind: {self.kind}")


@dataclass(frozen=True)
class World:
    family_id: str
    concept_to_token: Dict[str, str]
    order: Tuple[str, ...]

    def encode(self, meaning: Meaning) -> str:
        pieces: List[str] = []
        for slot in self.order:
            if slot == "neg":
                if meaning.neg:
                    pieces.append(self.concept_to_token["neg:true"])
            elif slot == "action":
                pieces.append(self.concept_to_token[f"action:{meaning.action}"])
            elif slot == "object":
                pieces.append(self.concept_to_token[f"object:{meaning.object}"])
            elif slot == "color":
                pieces.append(self.concept_to_token[f"color:{meaning.color}"])
            elif slot == "count":
                pieces.append(self.concept_to_token[f"count:{meaning.count}"])
            else:
                raise ValueError(f"unknown slot: {slot}")
        return " ".join(pieces)

    def example(self, meaning: Meaning) -> Example:
        return Example(command=self.encode(meaning), meaning=meaning)

    def rulebook_text(self) -> str:
        lines = ["Current MiniLang rulebook:", f"- word_order: {' '.join(self.order)}"]
        for concept, token in sorted(self.concept_to_token.items()):
            lines.append(f"- {concept} -> {token}")
        lines.append("- omit neg token when neg=false")
        return "\n".join(lines)


@dataclass(frozen=True)
class Episode:
    episode_id: str
    world: World
    examples: List[Example]
    tasks: List[Task]


def make_world(rng: random.Random, family_id: str, *, order: Optional[Tuple[str, ...]] = None) -> World:
    concepts = [f"action:{value}" for value in ACTIONS]
    concepts += [f"object:{value}" for value in OBJECTS]
    concepts += [f"color:{value}" for value in COLORS]
    concepts += [f"count:{value}" for value in COUNTS]
    concepts += ["neg:true"]

    tokens = list(VOCAB)
    rng.shuffle(tokens)
    if order is None:
        order = rng.choice(ORDERS)
    return World(
        family_id=family_id,
        concept_to_token={concept: token for concept, token in zip(concepts, tokens)},
        order=order,
    )


def random_meaning(rng: random.Random) -> Meaning:
    return Meaning(
        action=rng.choice(ACTIONS),
        object=rng.choice(OBJECTS),
        color=rng.choice(COLORS),
        count=rng.choice(COUNTS),
        neg=rng.random() < 0.25,
    )


def diagnostic_meanings(rng: random.Random) -> List[Meaning]:
    base_action = rng.choice(ACTIONS)
    base_object = rng.choice(OBJECTS)
    base_color = rng.choice(COLORS)
    base_count = rng.choice(COUNTS)

    meanings: List[Meaning] = []
    meanings.extend(Meaning(action, base_object, base_color, base_count) for action in ACTIONS)
    meanings.extend(Meaning(base_action, obj, base_color, base_count) for obj in OBJECTS)
    meanings.extend(Meaning(base_action, base_object, color, base_count) for color in COLORS)
    meanings.extend(Meaning(base_action, base_object, base_color, count) for count in COUNTS)
    meanings.append(Meaning(base_action, base_object, base_color, base_count, neg=True))
    rng.shuffle(meanings)
    return meanings


def support_examples(world: World, rng: random.Random, budget: int) -> List[Example]:
    meanings = diagnostic_meanings(rng)
    return [world.example(meaning) for meaning in meanings[:budget]]


def make_tasks(world: World, rng: random.Random, parse_count: int, generate_count: int) -> List[Task]:
    tasks: List[Task] = []
    for idx in range(parse_count):
        meaning = random_meaning(rng)
        tasks.append(
            Task(
                task_id=f"p{idx}",
                kind="parse",
                command=world.encode(meaning),
                meaning=meaning,
            )
        )
    for idx in range(generate_count):
        meaning = random_meaning(rng)
        tasks.append(
            Task(
                task_id=f"g{idx}",
                kind="generate",
                command=world.encode(meaning),
                meaning=meaning,
            )
        )
    rng.shuffle(tasks)
    return tasks


def make_episode(
    seed: int,
    *,
    support_budget: int = 12,
    parse_tasks: int = 4,
    generate_tasks: int = 4,
) -> Episode:
    rng = random.Random(seed)
    world = make_world(rng, family_id=f"family-{seed}")
    examples = support_examples(world, random.Random(seed + 10_000), support_budget)
    tasks = make_tasks(world, random.Random(seed + 20_000), parse_tasks, generate_tasks)
    return Episode(
        episode_id=f"episode-{seed}",
        world=world,
        examples=examples,
        tasks=tasks,
    )


def normalized_command(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def all_expected_answers(world: World, tasks: Sequence[Task]) -> List[Dict[str, object]]:
    answers: List[Dict[str, object]] = []
    for task in tasks:
        if task.kind == "parse" and task.meaning is not None:
            answers.append({"task_id": task.task_id, "meaning": task.meaning.to_dict()})
        elif task.kind == "generate" and task.meaning is not None:
            answers.append({"task_id": task.task_id, "command": world.encode(task.meaning)})
    return answers

