import serial
import time
import csv

def open_serial_connection(port):
    ser = serial.Serial(f'COM{port}', 9600, timeout=1)
    ser.flush()
    return ser

def get_weight(ser):
    ser.write(b'\x4F\x38\r\n')
    start_time = time.time()

    while time.time() - start_time < 2:
        line = ser.readline().decode('utf-8').rstrip()
        if line.startswith('+'):
            weight_data = line.split()
            return float(weight_data[1])

    return None

def main():
    num_balances = int(input("Enter number of balances (max 8): "))
    if num_balances > 8:
        print("Maximum of 8 balances allowed.")
        return

    com_ports = []
    for i in range(num_balances):
        com_ports.append(input(f"Enter COM port number for balance {i+1}: "))

    frequency = int(input("Enter the frequency of measurements in seconds: "))
    
    filename = input("Enter the name of the file (without spaces): ")
    while " " in filename:
        print("Filename should not contain spaces.")
        filename = input("Enter the name of the file (without spaces): ")

    filepath = f"{filename}.csv"

    sers = [open_serial_connection(port) for port in com_ports]
    fieldnames = ['Timestamp'] + [f'COM{port}_Weight' for port in com_ports]

    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

    print("Starting measurements...")

    while True:
        print_data = {"Timestamp": time.strftime('%Y-%m-%d %H:%M:%S')}
        for i, ser in enumerate(sers):
            weight = get_weight(ser)
            print_data[f'COM{com_ports[i]}_Weight'] = weight
            print(f"Weight at {print_data['Timestamp']} on COM{com_ports[i]}: {weight}")

        with open(filepath, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerow(print_data)

        time.sleep(frequency)

    for ser in sers:
        ser.close()

if __name__ == "__main__":
    main()
