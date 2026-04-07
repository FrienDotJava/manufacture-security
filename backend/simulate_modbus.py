from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('localhost', port=10502)
client.connect()

# Read pump status from Holding Register 0
result = client.read_holding_registers(address=0, count=1, device_id=1)
print(f"Pump status: {'ON' if result.registers[0] == 1 else 'OFF'}")

client.close()