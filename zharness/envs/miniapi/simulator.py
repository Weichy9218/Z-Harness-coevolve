"""Small stateful API workflow simulator with hidden harness constraints."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import random
from typing import Dict, Iterable, List, Sequence, Tuple


COUPON_PHASES = ("before_reserve", "after_reserve")
CARRIER_MAPS = (
    {"standard": "ground", "priority": "air"},
    {"standard": "postal", "priority": "fastship"},
)
UNIT_PRICES = (90, 110, 130)
DISCOUNTS = (7, 13, 19)


@dataclass(frozen=True)
class MiniAPIGoal:
    order_id: str
    customer_id: str
    sku: str
    quantity: int
    priority: bool
    auth_token: str
    coupon_code: str
    unit_price: int
    discount: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class APIWorld:
    family_id: str
    coupon_phase: str
    requires_risk_check: bool
    receipt_before_ship: bool
    standard_carrier: str
    priority_carrier: str

    def rulebook_text(self) -> str:
        risk = "required before charge_payment" if self.requires_risk_check else "not required"
        receipt = "required before ship_order" if self.receipt_before_ship else "not required"
        return "\n".join(
            [
                "Current MiniAPI rulebook:",
                f"- coupon_phase: {self.coupon_phase}",
                f"- risk_check: {risk}",
                f"- receipt: {receipt}",
                f"- standard_carrier: {self.standard_carrier}",
                f"- priority_carrier: {self.priority_carrier}",
                "- authenticate before write tools",
                "- charge amount = unit_price * quantity - discount",
            ]
        )

    def expected_carrier(self, goal: MiniAPIGoal) -> str:
        if goal.priority:
            return self.priority_carrier
        return self.standard_carrier


@dataclass(frozen=True)
class APICall:
    name: str
    args: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return {"name": self.name, "args": dict(self.args)}


@dataclass(frozen=True)
class MiniAPIEpisode:
    episode_id: str
    world: APIWorld
    goal: MiniAPIGoal


@dataclass(frozen=True)
class APIExecutionResult:
    success: bool
    errors: Tuple[str, ...]
    final_state: Dict[str, object]
    trace: Tuple[Dict[str, object], ...]

    def to_metrics(self) -> Dict[str, float]:
        num_steps = max(len(self.trace), 1)
        completed = sum(
            1
            for key in ("authenticated", "created", "coupon_applied", "reserved", "paid", "shipped")
            if self.final_state.get(key)
        )
        forbidden = sum(1 for error in self.errors if error.startswith("forbidden"))
        required = 6
        if self.final_state.get("risk_required"):
            required += 1
            if self.final_state.get("risk_checked"):
                completed += 1
        if self.final_state.get("receipt_required"):
            required += 1
            if self.final_state.get("receipt_sent"):
                completed += 1

        return {
            "success": 1.0 if self.success else 0.0,
            "completion": completed / required,
            "robustness": max(0.0, 1.0 - len(self.errors) / num_steps),
            "tool_use": _tool_use_score(self.trace, self.final_state),
            "consistency": 1.0 if self.success or not self.errors else 0.0,
            "forbidden_action_rate": forbidden / num_steps,
            "num_steps": float(len(self.trace)),
            "num_errors": float(len(self.errors)),
        }


def make_episode(seed: int) -> MiniAPIEpisode:
    rng = random.Random(seed)
    world = make_world(rng, family_id=f"api-family-{seed}")
    goal = make_goal(rng, seed)
    return MiniAPIEpisode(episode_id=f"miniapi-{seed}", world=world, goal=goal)


def make_world(rng: random.Random, *, family_id: str) -> APIWorld:
    carriers = rng.choice(CARRIER_MAPS)
    return APIWorld(
        family_id=family_id,
        coupon_phase=rng.choice(COUPON_PHASES),
        requires_risk_check=rng.random() < 0.5,
        receipt_before_ship=rng.random() < 0.5,
        standard_carrier=carriers["standard"],
        priority_carrier=carriers["priority"],
    )


def make_goal(rng: random.Random, seed: int) -> MiniAPIGoal:
    return MiniAPIGoal(
        order_id=f"ord-{seed}",
        customer_id=f"cust-{rng.randrange(100, 999)}",
        sku=f"sku-{rng.randrange(10, 99)}",
        quantity=rng.choice((1, 2, 3)),
        priority=rng.random() < 0.5,
        auth_token=f"token-{seed}",
        coupon_code=f"SAVE{rng.randrange(10, 99)}",
        unit_price=rng.choice(UNIT_PRICES),
        discount=rng.choice(DISCOUNTS),
    )


def make_counterfactual_world(world: APIWorld) -> APIWorld:
    carrier_map = CARRIER_MAPS[1] if world.standard_carrier == CARRIER_MAPS[0]["standard"] else CARRIER_MAPS[0]
    coupon_phase = "after_reserve" if world.coupon_phase == "before_reserve" else "before_reserve"
    return APIWorld(
        family_id=f"{world.family_id}-counterfactual",
        coupon_phase=coupon_phase,
        requires_risk_check=not world.requires_risk_check,
        receipt_before_ship=not world.receipt_before_ship,
        standard_carrier=carrier_map["standard"],
        priority_carrier=carrier_map["priority"],
    )


def execute_plan(world: APIWorld, goal: MiniAPIGoal, calls: Sequence[APICall]) -> APIExecutionResult:
    state: Dict[str, object] = {
        "authenticated": False,
        "created": False,
        "coupon_applied": False,
        "reserved": False,
        "risk_checked": False,
        "paid": False,
        "receipt_sent": False,
        "shipped": False,
        "risk_required": world.requires_risk_check,
        "receipt_required": world.receipt_before_ship,
    }
    errors: List[str] = []
    trace: List[Dict[str, object]] = []

    for call in calls:
        before_errors = len(errors)
        _apply_call(world, goal, state, call, errors)
        observation = "ok" if len(errors) == before_errors else errors[-1]
        trace.append(
            {
                "call": call.to_dict(),
                "observation": observation,
                "state": dict(state),
            }
        )

    success = bool(state["shipped"]) and not errors
    return APIExecutionResult(
        success=success,
        errors=tuple(errors),
        final_state=state,
        trace=tuple(trace),
    )


def oracle_plan(world: APIWorld, goal: MiniAPIGoal) -> List[APICall]:
    calls = [
        APICall("authenticate", {"token": goal.auth_token}),
        APICall(
            "create_order",
            {
                "order_id": goal.order_id,
                "customer_id": goal.customer_id,
                "sku": goal.sku,
                "quantity": goal.quantity,
            },
        ),
    ]
    if world.coupon_phase == "before_reserve":
        calls.append(APICall("apply_coupon", {"order_id": goal.order_id, "coupon_code": goal.coupon_code}))
        calls.append(APICall("reserve_inventory", {"order_id": goal.order_id}))
    else:
        calls.append(APICall("reserve_inventory", {"order_id": goal.order_id}))
        calls.append(APICall("apply_coupon", {"order_id": goal.order_id, "coupon_code": goal.coupon_code}))
    if world.requires_risk_check:
        calls.append(APICall("risk_check", {"order_id": goal.order_id}))
    calls.append(APICall("charge_payment", {"order_id": goal.order_id, "amount": expected_amount(goal)}))
    if world.receipt_before_ship:
        calls.append(APICall("send_receipt", {"order_id": goal.order_id}))
    calls.append(APICall("ship_order", {"order_id": goal.order_id, "carrier": world.expected_carrier(goal)}))
    return calls


def naive_plan(goal: MiniAPIGoal) -> List[APICall]:
    return [
        APICall(
            "create_order",
            {
                "order_id": goal.order_id,
                "customer_id": goal.customer_id,
                "sku": goal.sku,
                "quantity": goal.quantity,
            },
        ),
        APICall("apply_coupon", {"order_id": goal.order_id, "coupon_code": goal.coupon_code}),
        APICall("reserve_inventory", {"order_id": goal.order_id}),
        APICall("charge_payment", {"order_id": goal.order_id, "amount": goal.unit_price * goal.quantity}),
        APICall("ship_order", {"order_id": goal.order_id, "carrier": "ground"}),
    ]


def diagnostic_probe_plan(world: APIWorld, goal: MiniAPIGoal) -> Tuple[List[APICall], List[Dict[str, object]]]:
    probe_trace: List[Dict[str, object]] = []
    for index, candidate in enumerate(_candidate_worlds(goal)):
        probe_goal = _probe_goal(goal, suffix=f"probe-{index}")
        calls = oracle_plan(candidate, probe_goal)
        result = execute_plan(world, probe_goal, calls)
        probe_trace.append(
            {
                "probe_id": probe_goal.order_id,
                "candidate": _candidate_summary(candidate),
                "success": result.success,
                "errors": list(result.errors),
            }
        )
        if result.success:
            return oracle_plan(candidate, goal), probe_trace
    return naive_plan(goal), probe_trace


def expected_amount(goal: MiniAPIGoal) -> int:
    return goal.unit_price * goal.quantity - goal.discount


def _apply_call(
    world: APIWorld,
    goal: MiniAPIGoal,
    state: Dict[str, object],
    call: APICall,
    errors: List[str],
) -> None:
    if call.name != "authenticate" and not state["authenticated"]:
        errors.append(f"forbidden:{call.name}:missing_auth")
        return

    if call.name == "authenticate":
        if call.args.get("token") != goal.auth_token:
            errors.append("forbidden:authenticate:bad_token")
            return
        state["authenticated"] = True
        return

    if call.name == "create_order":
        if call.args.get("order_id") != goal.order_id or int(call.args.get("quantity", 0)) != goal.quantity:
            errors.append("invalid:create_order:goal_mismatch")
            return
        state["created"] = True
        return

    if call.name == "apply_coupon":
        if not state["created"]:
            errors.append("invalid:apply_coupon:no_order")
            return
        if call.args.get("coupon_code") != goal.coupon_code:
            errors.append("invalid:apply_coupon:bad_code")
            return
        if world.coupon_phase == "before_reserve" and state["reserved"]:
            errors.append("invalid:apply_coupon:must_precede_reserve")
            return
        if world.coupon_phase == "after_reserve" and not state["reserved"]:
            errors.append("invalid:apply_coupon:must_follow_reserve")
            return
        state["coupon_applied"] = True
        return

    if call.name == "reserve_inventory":
        if not state["created"]:
            errors.append("invalid:reserve_inventory:no_order")
            return
        if world.coupon_phase == "before_reserve" and not state["coupon_applied"]:
            errors.append("invalid:reserve_inventory:coupon_required_first")
            return
        state["reserved"] = True
        return

    if call.name == "risk_check":
        if not state["reserved"]:
            errors.append("invalid:risk_check:not_reserved")
            return
        state["risk_checked"] = True
        return

    if call.name == "charge_payment":
        if not state["reserved"] or not state["coupon_applied"]:
            errors.append("invalid:charge_payment:not_ready")
            return
        if world.requires_risk_check and not state["risk_checked"]:
            errors.append("invalid:charge_payment:risk_check_required")
            return
        if int(call.args.get("amount", -1)) != expected_amount(goal):
            errors.append("invalid:charge_payment:bad_amount")
            return
        state["paid"] = True
        return

    if call.name == "send_receipt":
        if not state["paid"]:
            errors.append("invalid:send_receipt:not_paid")
            return
        state["receipt_sent"] = True
        return

    if call.name == "ship_order":
        if not state["paid"]:
            errors.append("invalid:ship_order:not_paid")
            return
        if world.receipt_before_ship and not state["receipt_sent"]:
            errors.append("invalid:ship_order:receipt_required")
            return
        if call.args.get("carrier") != world.expected_carrier(goal):
            errors.append("invalid:ship_order:bad_carrier")
            return
        state["shipped"] = True
        return

    errors.append(f"invalid:{call.name}:unknown_tool")


def _candidate_worlds(goal: MiniAPIGoal) -> Iterable[APIWorld]:
    for coupon_phase in COUPON_PHASES:
        for requires_risk_check in (False, True):
            for receipt_before_ship in (False, True):
                for carriers in CARRIER_MAPS:
                    yield APIWorld(
                        family_id=f"candidate-{coupon_phase}-{requires_risk_check}-{receipt_before_ship}",
                        coupon_phase=coupon_phase,
                        requires_risk_check=requires_risk_check,
                        receipt_before_ship=receipt_before_ship,
                        standard_carrier=carriers["standard"],
                        priority_carrier=carriers["priority"],
                    )


def _probe_goal(goal: MiniAPIGoal, *, suffix: str) -> MiniAPIGoal:
    return MiniAPIGoal(
        order_id=f"{goal.order_id}-{suffix}",
        customer_id=f"{goal.customer_id}-{suffix}",
        sku=goal.sku,
        quantity=goal.quantity,
        priority=goal.priority,
        auth_token=goal.auth_token,
        coupon_code=goal.coupon_code,
        unit_price=goal.unit_price,
        discount=goal.discount,
    )


def _candidate_summary(world: APIWorld) -> Dict[str, object]:
    return {
        "coupon_phase": world.coupon_phase,
        "requires_risk_check": world.requires_risk_check,
        "receipt_before_ship": world.receipt_before_ship,
        "standard_carrier": world.standard_carrier,
        "priority_carrier": world.priority_carrier,
    }


def _tool_use_score(trace: Sequence[Dict[str, object]], state: Dict[str, object]) -> float:
    names = [str(step.get("call", {}).get("name")) for step in trace]
    required = {"authenticate", "create_order", "apply_coupon", "reserve_inventory", "charge_payment", "ship_order"}
    if state.get("risk_required"):
        required.add("risk_check")
    if state.get("receipt_required"):
        required.add("send_receipt")
    if not required:
        return 0.0
    return len(required.intersection(names)) / len(required)
