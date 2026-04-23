import asyncio
import time
import logging
from pymodbus.client import ModbusTcpClient
import httpx
from pathlib import Path
import os

LOG_PATH = Path(__file__).with_name("injection.log")

logger = logging.getLogger("fault_injection")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

MODBUS_HOST = os.getenv("MODBUS_HOST", "localhost")
MODBUS_PORT = 10502
DEVICE_ID = 1

PUMP_STATUS_REGISTER = 0

NODE_RED_BASE_URL = os.getenv("NODERED_URL", "http://localhost:1880")

INJECT_NODE_ID = "f756e8fcd382fdff"

OBSERVATION_DELAY_SECONDS = 2.0

FAULT_SCENARIOS = [
    {
        "name": "Normal Operation Baseline",
        "description": (
            "Water level at 25 (normal operating range, below fill threshold of 30). "
            "Pump should be ON to continue filling the tank."
        ),
        "inject_level": 25,
        "expected_pump_after_reaction": 1,
        "expected_behavior_rationale": (
            "Level 25 < threshold 30 (numeric) → switch rule 1 → Payload True → pump=1 ON. "
            "This is the expected safe normal operating state."
        ),
        "architectural_gap": False,
    },
    {
        "name": "High Level Cutoff",
        "description": (
            "Water level at 35 (above fill threshold of 30). "
            "Pump should turn OFF — tank is sufficiently full."
        ),
        "inject_level": 35,
        "expected_pump_after_reaction": 0,
        "expected_behavior_rationale": (
            "Level 35 >= threshold 30 (numeric) → switch rule 2 → Payload False → pump=0 OFF. "
            "This is the expected safe high-level cutoff state."
        ),
        "architectural_gap": False,
    },
    {
        "name": "Overflow Fault Injection",
        "description": (
            "Water level at 110 (110% of capacity — physically impossible, indicates sensor fault "
            "or catastrophic overflow). Pump should be OFF, but the flow has NO dedicated rule "
            "for values above 100. The >= 30 rule catches it, but no overflow alarm is raised."
        ),
        "inject_level": 110,
        "expected_pump_after_reaction": 0,
        "expected_behavior_rationale": (
            "Level 110 >= 30 (numeric) → switch rule 2 → pump=0 OFF. "
            "The pump turns off correctly, BUT there is no upper-bound ceiling rule (e.g., > 100) "
            "to distinguish a legitimate high reading from a physically impossible/faulty one. "
            "A value of 110% should trigger an alarm or fail-safe halt, not silently route to "
            "the same output as level=35. This is an ARCHITECTURAL_GAP: missing overflow alarm "
            "and sensor-range validation logic."
        ),
        "architectural_gap": True,
    },
    {
        "name": "Sensor Dropout / Zero Reading",
        "description": (
            "Water level reads 0. This is ambiguous: it could mean the tank is truly empty, "
            "OR the sensor has disconnected (both produce register value 0). "
            "The flow cannot distinguish these cases and blindly turns the pump ON."
        ),
        "inject_level": 0,
        "expected_pump_after_reaction": None,
        "expected_behavior_rationale": (
            "Level 0 < threshold 30 → switch rule 1 → pump=1 ON. "
            "The flow turns the pump on, but cannot distinguish an empty tank from a dead sensor. "
            "There is no minimum-valid-reading check, no sensor health monitoring, "
            "and no deadman/watchdog timer to cut the pump if the level never rises. "
            "A disconnected sensor will run the pump indefinitely — ARCHITECTURAL_GAP."
        ),
        "architectural_gap": True,
    },
    {
        "name": "Negative Sensor Reading",
        "description": (
            "Water level reads -1 (physically impossible — indicates sensor wiring fault or "
            "integer underflow in upstream logic). No validation exists in the flow."
        ),
        "inject_level": -1,
        "expected_pump_after_reaction": None,
        "expected_behavior_rationale": (
            "Level -1 < threshold 30 → switch rule 1 → pump=1 ON. "
            "A negative reading is physically impossible and should be rejected as invalid. "
            "The flow has no lower-bound validation (e.g., < 0 → fault), so it treats "
            "a broken sensor reading as a legitimate low-tank signal — ARCHITECTURAL_GAP."
        ),
        "architectural_gap": True,
    },
]

def read_pump_status() -> dict:
    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
    connected = client.connect()
    if not connected:
        return {"success": False, "error": "Could not connect to Modbus server", "pump_register_value": None}
    try:
        result = client.read_holding_registers(address=PUMP_STATUS_REGISTER, count=1, device_id=DEVICE_ID)
        if result.isError():
            return {"success": False, "error": str(result), "pump_register_value": None}
        value = result.registers[0]
        return {
            "success": True,
            "pump_register_value": value,
            "pump_is_on": value == 1,
            "pump_state_label": "ON" if value == 1 else "OFF",
        }
    except Exception as e:
        logger.exception("Error reading pump status register")
        return {"success": False, "error": str(e), "pump_register_value": None}
    finally:
        client.close()


def inject_simulation_data(level: int) -> dict:
    url = f"{NODE_RED_BASE_URL}/api/level"
    payload = {"payload": level, "payloadType": "num"}

    logger.info("Injecting water level=%s to inject node %s", level, INJECT_NODE_ID)

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=payload)
            success = response.status_code == 200
            return {
                "success": success,
                "injected_level": level,
                "http_status": response.status_code,
                "timestamp": time.time(),
                "node_id": INJECT_NODE_ID,
                "error": None if success else f"HTTP {response.status_code}: {response.text}",
            }
    except Exception as e:
        logger.exception("Injection HTTP call failed")
        return {
            "success": False,
            "injected_level": level,
            "http_status": None,
            "timestamp": time.time(),
            "node_id": INJECT_NODE_ID,
            "error": str(e),
        }


async def observe_pump_behavior(scenario: dict) -> dict:
    scenario_name  = scenario["name"]
    inject_level   = scenario["inject_level"]
    expected_pump  = scenario["expected_pump_after_reaction"]
    is_arch_gap    = scenario.get("architectural_gap", False)

    logger.info("Scenario: %s (level=%s)", scenario_name, inject_level)

    before = read_pump_status()
    logger.info("Before injection: pump=%s", before.get("pump_state_label", "UNKNOWN"))

    injection = inject_simulation_data(inject_level)
    if not injection["success"]:
        logger.warning("Injection failed for scenario '%s': %s", scenario_name, injection["error"])

    logger.info("Waiting %.1fs for Node-RED to react...", OBSERVATION_DELAY_SECONDS)
    await asyncio.sleep(OBSERVATION_DELAY_SECONDS)

    after = read_pump_status()
    logger.info("After injection: pump=%s", after.get("pump_state_label", "UNKNOWN"))

    observed_pump = after.get("pump_register_value")

    if is_arch_gap and expected_pump is None:
        verdict = "ARCHITECTURAL_GAP"
        verdict_detail = (
            f"System responded with pump={'ON' if observed_pump == 1 else 'OFF'} "
            f"for injected level={inject_level}. "
            "No defined safe expected state exists because the flow is missing "
            "sensor-validity, range-validation, or fail-safe logic for this condition."
        )
    elif is_arch_gap and expected_pump is not None and observed_pump == expected_pump:
        verdict = "PASS_WITH_ARCHITECTURAL_GAP"
        verdict_detail = (
            f"Pump is {'ON' if observed_pump == 1 else 'OFF'} as expected for level={inject_level}. "
            "However, the flow reaches this state via a generic rule rather than explicit "
            "range validation, and raises no alarm for the abnormal input value. "
            "Missing: upper-bound ceiling rule, overflow alarm, or sensor-fault escalation."
        )
    elif expected_pump is not None and observed_pump == expected_pump:
        verdict = "PASS"
        verdict_detail = (
            f"Pump is {'ON' if observed_pump == 1 else 'OFF'} as expected for level={inject_level}."
        )
    else:
        verdict = "CRITICAL_SAFETY_VIOLATION"
        verdict_detail = (
            f"Expected pump={'ON' if expected_pump == 1 else 'OFF'} "
            f"but observed pump={'ON' if observed_pump == 1 else 'OFF'} "
            f"after injecting level={inject_level}. "
            "The flow produced a DANGEROUS actuator state."
        )

    logger.info("Verdict: %s", verdict)

    return {
        "scenario_name": scenario_name,
        "scenario_description": scenario["description"],
        "injected_level": inject_level,
        "expected_pump_state": (
            "ON" if expected_pump == 1
            else "OFF" if expected_pump == 0
            else "UNDEFINED"
        ),
        "observed_pump_state_before": before.get("pump_state_label", "READ_ERROR"),
        "observed_pump_state_after": after.get("pump_state_label", "READ_ERROR"),
        "observed_pump_register_value": observed_pump,
        "injection_success": injection["success"],
        "injection_error": injection.get("error"),
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "expected_behavior_rationale": scenario["expected_behavior_rationale"],
    }


async def run_all_fault_scenarios() -> list[dict]:
    results = []
    for scenario in FAULT_SCENARIOS:
        result = await observe_pump_behavior(scenario)
        results.append(result)

        await asyncio.sleep(1.0)
    return results