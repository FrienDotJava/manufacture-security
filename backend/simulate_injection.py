from pymodbus.client import ModbusTcpClient
import httpx
import time

modbus_client = ModbusTcpClient('localhost', port=10502)
modbus_client.connect()

NODE_RED_BASE_URL = "http://localhost:1880"

level = 25

url = f"{NODE_RED_BASE_URL}/api/level"
payload = {"payload": level, "payloadType": "num"}

print(f"Injecting water level={level} to {url}")

try:
    with httpx.Client(timeout=5.0) as client:
        response = client.post(url, json=payload)
        success = response.status_code == 200

        time.sleep(1)

        result = modbus_client.read_holding_registers(address=0, count=1, device_id=1)
        
        if not result.isError():
            print(f"Pump status: {'ON' if result.registers[0] == 1 else 'OFF'}")
        else:
            print(f"Failed to read Modbus register. Device returned error.")

        print({
            "success": success,
            "injected_level": level,
            "http_status": response.status_code,
            "timestamp": time.time(),
            "error": None if success else f"HTTP {response.status_code}: {response.text}",
        })
except Exception as e:
    print("Injection HTTP call failed")
    print({
        "success": False,
        "injected_level": level,
        "http_status": None,
        "timestamp": time.time(),
        "error": str(e),
    })
finally:
    modbus_client.close()