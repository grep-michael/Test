import os,sys,glob,shutil,time
from typing import *
from pathlib import *
import subprocess,datetime,re
import xml.etree.ElementTree as ET
from xml.dom import minidom


# Config Parsing
APPLE_BASE = 'Logs/Apple'
MOUNT_BASE = "/mnt/itad_share"

CONFIG: Dict[str, Any] = {}

def load_env_config(env_file: str = ".env", encoding: str = "utf-8") -> Dict[str, Any]:

    global CONFIG

    required_keys = [
        "FTP_USER",
        "FTP_PASS", 
        "FTP_HOST",
        "FTP_PORT",
        "SHARE_IP",
        "SHARE_NAME",
        "SHARE_USER",
        "SHARE_PASS"
    ]

    CONFIG.clear()  # Reset global config
    
    env_path = Path(env_file)
    if not env_path.exists():
        for key in required_keys:
            value = os.environ.get(key)
            if value is not None:  
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]              
                CONFIG[key] = value
        
        print(f"Loaded {len(CONFIG)} variables from system environment")
        return CONFIG
    
    with open(env_path, 'r', encoding=encoding) as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE format
            if '=' not in line:
                raise ValueError(f"Invalid format at line {line_num}: {line}")
            
            key, value = line.split('=', 1)  # Split only on first =
            key = key.strip()
            value = value.strip()
            
            # Remove quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            
            CONFIG[key] = value
    
    return CONFIG

def verify_env_config() -> bool:
    required_keys = [
        "FTP_USER",
        "FTP_PASS", 
        "FTP_HOST",
        "FTP_PORT",
        "SHARE_IP",
        "SHARE_NAME",
        "SHARE_USER",
        "SHARE_PASS"
    ]
    
    missing_keys = []
    empty_keys = []
    
    for key in required_keys:
        if key not in CONFIG:
            missing_keys.append(key)
        elif not CONFIG[key] or str(CONFIG[key]).strip() == "":
            empty_keys.append(key)
    
    # Report results
    if missing_keys:
        print(f"ERROR: Missing required environment variables: {', '.join(missing_keys)}")
    
    if empty_keys:
        print(f"ERROR: Empty environment variables: {', '.join(empty_keys)}")
    
    if missing_keys or empty_keys:
        print("Please check your .env file and reload configuration")
        return False
    
    print("✓ All required environment variables are present and populated")
    return True

load_env_config("CREDS.env")

if not verify_env_config():
    sys.exit(1)

# Share mounting



def is_share_mounted(mount_point: str) -> bool:
    """
    Check if the share is already mounted at the specified mount point.
    
    Args:
        mount_point: Path to check for existing mount
        
    Returns:
        True if mounted, False otherwise
    """
    try:
        # Check /proc/mounts for the mount point
        with open('/proc/mounts', 'r') as f:
            for line in f:
                fields = line.split()
                if len(fields) >= 2 and fields[1] == mount_point:
                    return True
        return False
    except Exception:
        return False

def unmount_share(mount_point: str = "/mnt/itad_share") -> bool:
    if not is_share_mounted(mount_point):
        print(f"No share mounted at {mount_point}")
        return True
    
    try:
        print(f"Unmounting {mount_point}...")
        result = subprocess.run(["sudo", "umount", mount_point], 
                              capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("Share unmounted successfully")
            return True
        else:
            print(f"Unmount failed: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"Error during unmount: {e}")
        return False

def mount_share(mount_point: str = "/mnt/itad_share") -> bool:
    share_ip = CONFIG["SHARE_IP"]
    share_name = CONFIG["SHARE_NAME"]
    share_user = CONFIG["SHARE_USER"]
    share_pass = CONFIG["SHARE_PASS"]
    
    if not all([share_ip, share_name, share_user, share_pass]):
        print("Error: Missing required share configuration in environment")
        return False
    
    # Create mount point if it doesn't exist
    mount_path = Path(mount_point)
    try:
        mount_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(f"Error: Permission denied creating mount point: {mount_point}")
        return False
    
    # Check if already mounted
    if is_share_mounted(mount_point):
        print(f"Share already mounted at {mount_point}")
        return True
    
    # Build the share URL
    share_url = f"//{share_ip}/{share_name}"
    
    # Mount command with credentials
    mount_cmd = [
        "sudo", "mount", "-t", "cifs", share_url, mount_point,
        "-o", f"username={share_user},password={share_pass},iocharset=utf8,file_mode=0777,dir_mode=0777"
    ]
    
    try:
        print(f"Mounting {share_url} to {mount_point}...")
        result = subprocess.run(mount_cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("Share mounted successfully")
            return True
        else:
            print(f"Mount failed: {result.stderr.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        print("Mount operation timed out")
        return False
    except FileNotFoundError:
        print("Error: 'mount' command not found. Ensure cifs-utils is installed.")
        return False
    except Exception as e:
        print(f"Unexpected error during mount: {e}")
        return False
    
successful_mount = mount_share()

if not successful_mount:
    sys.exit(1)


# File processing

## old steve jobs functions

def parse_input_txt(input_text):
    data = {}
    pattern2 = r'(.*):(.*)'
    matches = re.findall(pattern2, input_text)

    for key, value in matches:
        data[key] = value
        # print(key)
    #     print(key + " " + value)

    return data

def extract_total_cores(input_text):
    global errors
    # Extract Total Cores
    try:
        pattern = r"Total Number of Cores:\s+(\d+)"
        cores_values = [int(val) for val in re.findall(pattern, input_text)]
    except:
        print("NUM CORES ERROR")
        errors += "NUM CORES ERROR\n"
    # print(cores_values)
    return cores_values

## new functions

def get_all_text_files():
    path = os.path.join(MOUNT_BASE,APPLE_BASE,"Temp","*.txt")
    res = glob.glob(path)
    return res

RAW_LOGS = get_all_text_files()
ERRORS = ""

def clear_collision(xml_log):
    log_dir = os.path.join(MOUNT_BASE,APPLE_BASE,"Processed")
    log_file = os.path.join(log_dir,xml_log)

    if os.path.isfile(log_file):
        print(f"Collision detected: {log_file}")

        modification_time = datetime.datetime.fromtimestamp(
            os.path.getmtime(log_file)
            ).strftime('_%m-%d-%Y_%H-%M-%S')

        new_log_name = xml_log[:-4] + str(modification_time) + xml_log[-4:]
        new_log_path = os.path.join(log_dir,new_log_name)
        os.rename(log_file,
                new_log_path)
    
    return log_file

MAC_OS_DICT = {"11": "OSX", "12": "MacOS Sierra", "13": "MacOS High Sierra", "14": "MacOS Mojave", "15": "MacOS Catalina",
             "16": "MacOS Big Sur", "17": "MacOS Monterey", "18": "MacOS Ventura", "19": "MacOS Sonoma"}
GRADE_DICT = {"A": "A - No signs of wear", "B": "B - Minor to moderate signs of wear",
             "C": "C - Moderate to heavy signs of wear", "D": "D - Major signs of wear", "F": "F - Failed"}
APPLE_MODEL_DICT = {"Apple M1": "3.2", "Apple M1 Pro": "3.2", "Apple M1 Max": "3.2", "Apple M2": "3.49",
              "Apple M2 Pro": "3.49", "Apple M2 Max": "3.68"}
RAM_SPEED_DICT = {"Apple M1": "4266", "Apple M1 Pro": "6400", "Apple M1 Max": "6400", "Apple M2": "6400",
           "Apple M2 Pro": "6400", "Apple M2 Max": "6400"}
ASSET_CATEGORY_DICT = {"L": "Laptop", "D": "Desktop", "A": "All-In-One"}
displayDict = {"1920x1080": "(16:9)", "1280x720": "(16:9)", "1366x768": "(16:9)", "1600x900": "(16:9)", "2560x1440": "(16:9)",
               "3840x2160": "(16:9)", "1280x800": "(16:10)", "1440x900": "(16:10)", "1680x1050": "(16:10)", "1920x1200": "(16:10)",
                "2256x1504": "(3:2)", "3000x2000": "(3:2)", "2736x1824": "(3:2)", "2304x1440": "(16:10)", "3024x1964": "(16:10)", "2560x1600": "(16:10)", "3072x1920": "(16:10)", "2880x1800": "(16:10)", "5120x2880": "(16:10)", "1024x768": "(4:3)", "3440x1440": "(21:9)"}

def create_xml(output_data, total_cores, input_text):
    global ERRORS
    SERIALNUM = ""
    batterycon = ""
    if '          Condition' in output_data:
        if output_data['          Condition'].split()[0] == "Normal":
            batterycon = "Pass"
        else:
            batterycon = "Fail"
    # SYSINFO
    sysinfo = ET.Element('SYSINFO')

    # SYSTEM_INVENTORY
    system_inventory = ET.SubElement(sysinfo, 'SYSTEM_INVENTORY')

    # /// System_Information
    system_info = ET.SubElement(system_inventory, 'System_Information')

    # Extract TECHID
    if 'TECHID' in output_data:
        ET.SubElement(system_info, 'Tech_ID').text = output_data['TECHID'].upper()
    else:
        ET.SubElement(system_info, 'Tech_ID').text = ""

    # Extract UID
    if 'SYSUID' in output_data:
        ET.SubElement(system_info, 'Asset_Identifier').text = output_data['SYSUID'].upper()
    else:
        ET.SubElement(system_info, 'Asset_Identifier').text = ""

    # Extract Form Factor
    if 'SYSTYPE' in output_data:
        if output_data["SYSTYPE"].upper() in ASSET_CATEGORY_DICT:
            ET.SubElement(system_info, 'System_Chassis_Type').text = ASSET_CATEGORY_DICT[output_data["SYSTYPE"].upper()]
        else:
            ET.SubElement(system_info, 'System_Chassis_Type').text = ""
    else:
        ET.SubElement(system_info, 'System_Chassis_Type').text = ""

    # Input Manufacturer
    ET.SubElement(system_info, 'System_Manufacturer').text = "APPLE"

    # Extract Model Number
    if 'BUILDNO' in output_data:
        ET.SubElement(system_info, 'System_ProductName').text = output_data['BUILDNO'].upper()
    else:
        ET.SubElement(system_info, 'System_ProductName').text = ""

    # Extract Serial Number
    if '      Serial Number (system)' in output_data:
        ET.SubElement(system_info, 'System_Serial_Number').text = output_data['      Serial Number (system)'].strip()
    else:
        ET.SubElement(system_info, 'System_Serial_Number').text = ""

    # Extract User Notes
    if 'SYSNOTES' in output_data:
        if batterycon == "Fail":
            ET.SubElement(system_info, 'System_UUID').text = output_data['SYSNOTES'].upper() + ", BATTERY SERVICE RECOMMENDED"
        else:
            ET.SubElement(system_info, 'System_UUID').text = output_data['SYSNOTES'].upper()
    else:
        if batterycon == "Fail":
            ET.SubElement(system_info, 'System_UUID').text = "" + "BATTERY SERVICE RECOMMENDED"
        else:
            ET.SubElement(system_info, 'System_UUID').text = ""

    # Extract Installed OS
    if 'OSVER' in output_data:
        if output_data['OSVER'] in MAC_OS_DICT:
            ET.SubElement(system_info, 'System_Version').text = MAC_OS_DICT[output_data['OSVER']]
        else:
            ET.SubElement(system_info, 'System_Version').text = ""
    else:
        ET.SubElement(system_info, 'System_Version').text = ""

    # Extract Drive Serial Number
    try:
        if re.search(r"NVMExpress:(.*?)\n\S", input_text, re.DOTALL) is not None:
            match = re.search(r"NVMExpress:(.*?)\n\S", input_text, re.DOTALL).group(1)
            SERIALNUM = re.search(r"Serial Number:\s*([\w-]+)", match, re.DOTALL).group(1)
            ET.SubElement(system_info, 'System_Memory').text = SERIALNUM.upper()
        elif re.search(r"SATA/SATA Express:(.*?)\n\S", input_text, re.DOTALL) is not None:
            match = re.search(r"SATA/SATA Express:(.*?)\n\S", input_text, re.DOTALL).group(1)
            SERIALNUM = re.search(r"Serial Number:\s*([\w-]+)", match, re.DOTALL).group(1)
            ET.SubElement(system_info, 'System_Memory').text = SERIALNUM.upper()
        elif re.search(r"SATA:(.*?)\n\S", input_text, re.DOTALL) is not None:
            match = re.search(r"SATA:(.*?)\n\S", input_text, re.DOTALL).group(1)
            SERIALNUM = re.search(r"Serial Number:\s*([\w-]+)", match, re.DOTALL).group(1)
            ET.SubElement(system_info, 'System_Memory').text = SERIALNUM.upper()
        else:
            SERIALNUM = ""
            ET.SubElement(system_info, 'System_Memory').text = ""
    except:
        ET.SubElement(system_info, 'System_Memory').text = ""
        print("DRIVE SERIAL NUM ERROR/NO DRIVE PRESENT")
        ERRORS += "DRIVE SERIAL NUM ERROR/NO DRIVE PRESENT\n"

    # Extract Final Grade
    if 'FINALGRADE' in output_data:
        ET.SubElement(system_info, 'Original_Product_Key').text = output_data['FINALGRADE'].upper()
    else:
        ET.SubElement(system_info, 'Original_Product_Key').text = ""

    # Extract Display Resolution
    if '          Resolution' in output_data:
        if output_data['SYSTYPE'].upper() == "A":
            ET.SubElement(system_info, 'Display_Resolution').text = output_data['          Resolution'].split()[0] + \
                                                                    output_data['          Resolution'].split()[1] + \
                                                                    output_data['          Resolution'].split()[2] + " (16:9)"
        else:
            ET.SubElement(system_info, 'Display_Resolution').text = output_data['          Resolution'].split()[0] + \
                                                                    output_data['          Resolution'].split()[1] + \
                                                                    output_data['          Resolution'].split()[2] + " (16:10)"
    else:
        ET.SubElement(system_info, 'Display_Resolution').text = ""

    # Extract Display Size
    if 'SCREENSIZE' in output_data:
        ET.SubElement(system_info, 'Display_Size_Est').text = output_data["SCREENSIZE"].upper() + '"'
    else:
        ET.SubElement(system_info, 'Display_Size_Est').text = ""

    # Input Drive Erasure Method
    ET.SubElement(system_info, 'MAC_Address').text = "NIST 800-88"

    if 'SYSCOLOR' in output_data:
        ET.SubElement(system_info, 'Color').text = output_data['SYSCOLOR'].upper()
    else:
        ET.SubElement(system_info, 'Color').text = ""

    # /// System_Information

    # /// Devices
    devices = ET.SubElement(system_inventory, 'Devices')
    # Input Network Device
    ET.SubElement(devices, 'Network_Device').text = ''
    # Input Drive Count
    if SERIALNUM != "":
        ET.SubElement(devices, 'Multimedia').text = '1'
    else:
        ET.SubElement(devices, 'Multimedia').text = '0'
    # Input Webcam Type
    ET.SubElement(devices, 'USB_Controller').text = 'FaceTime HD Camera (Built-in)'

    # Extract CPU Model
    try:
        if output_data['CPUNAME'].split()[0] == "Apple":
            ET.SubElement(devices, 'Video_Adapter').text = output_data['CPUNAME'] + " " + str(total_cores[0]) + "-CORE"
        else:
            ET.SubElement(devices, 'Video_Adapter').text = output_data['      Chipset Model'].strip()
    except:
        ET.SubElement(devices, 'Video_Adapter').text = ""
        print("CPU MODEL ERROR")
        ERRORS += "CPU MODEL ERROR\n"

    # Extract Form Factor
    if 'SYSTYPE' in output_data:
        if output_data['SYSTYPE'].upper() in ASSET_CATEGORY_DICT:
            ET.SubElement(devices, 'Data_Aquisition').text = ASSET_CATEGORY_DICT[output_data["SYSTYPE"].upper()]
        else:
            ET.SubElement(devices, 'Data_Aquisition').text = ""
    else:
        ET.SubElement(devices, 'Data_Aquisition').text = ""

    # Extract Cosmetic Grade
    if 'COSGRADE' in output_data:
        if output_data['COSGRADE'].upper() in GRADE_DICT:
            ET.SubElement(devices, 'Cardbus').text = GRADE_DICT[output_data['COSGRADE'].upper()]
        else:
            ET.SubElement(devices, 'Cardbus').text = ""
    else:
        ET.SubElement(devices, 'Cardbus').text = ""

    # Input Defects Causing Failure
    ET.SubElement(devices, 'Flash_Reader').text = 'N/A'
    # /// Devices

    # /// Processor
    processor = ET.SubElement(devices, 'Processor')

    # Extract CPU Specs for M1's/M2's
    try:
        if output_data['CPUNAME'].split()[0] == "Apple":
            # Extract CPU Model
            ET.SubElement(processor, 'Model').text = output_data['CPUNAME']
            # Extract CPU Speed
            if output_data['CPUNAME'] in APPLE_MODEL_DICT:
                ET.SubElement(processor, 'Speed').text = APPLE_MODEL_DICT[output_data['CPUNAME']] + " GHz"
            else:
                ET.SubElement(processor, 'Speed').text = ""
            # Extract CPU Cores
            ET.SubElement(processor, 'Cores').text = str(total_cores[1])
            # Extract CPU Name
            ET.SubElement(processor, 'Type').text = output_data['CPUNAME']


        # Extract CPU Specs for Intel Processors
        else:
            # Extract CPU Model
            if output_data['CPUNAME'].split()[1] == "Xeon(R)":
                ET.SubElement(processor, 'Model').text = output_data['CPUNAME'].split()[3] + " " + output_data['CPUNAME'].split()[4]
            else:
                ET.SubElement(processor, 'Model').text = output_data['CPUNAME'].split()[2]
            # Extract CPU Speed
            ET.SubElement(processor, 'Speed').text = output_data['      Processor Speed'].split()[0] + " GHz"
            # Extract CPU Cores
            ET.SubElement(processor, 'Cores').text = str(total_cores[0])
            # Extract CPU Name
            if len(output_data['      Processor Name'].split()) > 3:
                ET.SubElement(processor, 'Type').text = output_data['      Processor Name'].split()[1] + " " + \
                                                        output_data['      Processor Name'].split()[2] + " " + \
                                                        output_data['      Processor Name'].split()[3]
            else:
                ET.SubElement(processor, 'Type').text = output_data['      Processor Name'].split()[0] + " " + \
                                                        output_data['      Processor Name'].split()[1] + " " + \
                                                        output_data['      Processor Name'].split()[2]
    except:
        ET.SubElement(processor, 'Model').text = ""
        ET.SubElement(processor, 'Speed').text = ""
        ET.SubElement(processor, 'Cores').text = ""
        ET.SubElement(processor, 'Type').text = ""
        print("CPU SPECS ERROR")
        ERRORS += "CPU SPECS ERROR\n"
    # /// Processor

    # /// Memory
    memory = ET.SubElement(devices, 'Memory')

    # Input RAM Count
    ET.SubElement(memory, 'FormFactor').text = "2"

    # Extract RAM Speed
    try:
        if (output_data['CPUNAME'] in APPLE_MODEL_DICT):
            RAMSPEED = RAM_SPEED_DICT[output_data['CPUNAME']]
        else:
            memorytemp = re.search(r"\nMemory:(.*?)\n\S", input_text, re.DOTALL).group(1)
            pattern4 = r"Speed:\s*(\w+)"
            for match in re.finditer(pattern4, memorytemp, re.DOTALL):
                if match.group(1) != " Empty":
                    RAMSPEED = match.group(1)
            # print(RAMSPEED)
        ET.SubElement(memory, 'Speed').text = RAMSPEED + " MHz"
    except:
        ET.SubElement(memory, 'Speed').text = ""
        print("RAM SPEED ERROR")
        ERRORS += "RAM SPEED ERROR\n"

    # Extract RAM Size
    try:
        pattern5 = r"Hardware:.*?Memory:\s*(\w+)"
        RAMSIZE = re.search(pattern5, input_text, re.DOTALL).group(1)
        ET.SubElement(memory, 'Size').text = RAMSIZE + " GB"
    except:
        ET.SubElement(memory, 'Size').text = ""
        print("RAM SIZE ERROR")
        ERRORS += "RAM SIZE ERROR\n"

    # Extract RAM Type
    try:
        if ("Apple M" in output_data["CPUNAME"]):
            ET.SubElement(memory, 'Type').text = "INTEGRATED"
        else:
            # pattern6 = r"Memory Slots:.*?Type:\s*(\w+)"
            # RAMTYPE = re.search(pattern6, input_text, re.DOTALL).group(1)
            # ET.SubElement(memory, 'Type').text = RAMTYPE
            typetemp = re.search(r"\nMemory:(.*?)\n\S", input_text, re.DOTALL).group(1)
            pattern4 = r"Type:\s*(\w+)"
            for match in re.finditer(pattern4, typetemp, re.DOTALL):
                if match.group(1) != " Empty":
                    RAMTYPE = match.group(1)
            ET.SubElement(memory, 'Type').text = RAMTYPE
    except:
        ET.SubElement(memory, 'Type').text = ""
        print("RAM TYPE ERROR")
        ERRORS += "RAM TYPE ERROR\n"
    # /// Memory

    # /// Optical
    optical = ET.SubElement(devices, 'Optical')

    # Input Optical Drive
    ET.SubElement(optical, 'Model').text = 'Not Present'
    # Extract LCD Grade
    if 'LCDGRADE' in output_data:
        if output_data['LCDGRADE'].upper() in GRADE_DICT:
            ET.SubElement(optical, 'Type').text = GRADE_DICT[output_data['LCDGRADE'].upper()]
        else:
            ET.SubElement(optical, 'Type').text = ""
    else:
        ET.SubElement(optical, 'Type').text = ""
    # /// Optical

    # /// Battery
    battery = ET.SubElement(devices, 'Battery')
    # Extract Cycle Count
    if '          Cycle Count' in output_data:
        ET.SubElement(battery, 'Health').text = output_data['          Cycle Count'].strip() + " CYCLES"
    else:
        ET.SubElement(battery, 'Health').text = ""
    # Extract Battery Disposition
    if '          Condition' in output_data:
        ET.SubElement(battery, 'Grade').text = "Passed - Included"
    else:
        ET.SubElement(battery, 'Grade').text = ""
    # Extract Battery Health Percentage
    if 'SYSBAT' in output_data:
        ET.SubElement(battery, 'Capacity').text = output_data['SYSBAT'].upper()
    else:
        ET.SubElement(battery, 'Capacity').text = ""
    # /// Battery

    # /// Storage
    if SERIALNUM != "":
        storage = ET.SubElement(devices, 'Storage')

        # Extract Drive Model
        try:
            if re.search(r"NVMExpress:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"NVMExpress:(.*?)\n\S", input_text, re.DOTALL).group(1)
                MODEL = re.search(r"Model:\s*(.*?)\n", match, re.DOTALL).group(1)
            elif re.search(r"SATA/SATA Express:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"SATA/SATA Express:(.*?)\n\S", input_text, re.DOTALL).group(1)
                MODEL = re.search(r"Model:\s*(.*?)\n", match, re.DOTALL).group(1)
            elif re.search(r"SATA:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"SATA:(.*?)\n\S", input_text, re.DOTALL).group(1)
                MODEL = re.search(r"Model:\s*(.*?)\n", match, re.DOTALL).group(1)
            else:
                MODEL = ""

            # Input Drive Model
            ET.SubElement(storage, 'Model').text = MODEL.strip()
        except:
            ET.SubElement(storage, 'Model').text = ""
            print("DRIVE MODEL ERROR")
            ERRORS += "DRIVE MODEL ERROR\n"

        # Input Drive Type
        try:
            # pattern9 = r"Storage:.*?Medium Type:\s*(.*?)\n"
            # pattern9 = r"SATA/SATA Express:.*?Medium Type:\s*(.*?)\n"
            # hddtype = re.search(pattern9, input_text, re.DOTALL).group(1)
            if re.search(r"NVMExpress:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"NVMExpress:(.*?)\n\S", input_text, re.DOTALL).group(1)
                if re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL) is not None:
                    hddtype = re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL).group(1)
                else:
                    match = re.search(r"Storage:(.*)", input_text, re.DOTALL).group(1)
                    hddtype = re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL).group(1)
            elif re.search(r"SATA/SATA Express:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"SATA/SATA Express:(.*?)\n\S", input_text, re.DOTALL).group(1)
                if re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL).group(1) is not None:
                    hddtype = re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL).group(1)
                else:
                    match = re.search(r"Storage:(.*?)", input_text, re.DOTALL).group(1)
                    hddtype = re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL).group(1)
            elif re.search(r"SATA:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"SATA:(.*?)\n\S", input_text, re.DOTALL).group(1)
                if re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL).group(1) is not None:
                    hddtype = re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL).group(1)
                else:
                    match = re.search(r"Storage:(.*?)", input_text, re.DOTALL).group(1)
                    hddtype = re.search(r"Medium Type:\s*(.*?)\n", match, re.DOTALL).group(1)

            hddtype = hddtype.split()[0]
            if hddtype.upper() == "SSD":
                ET.SubElement(storage, 'DeviceType').text = "SSD"
            elif hddtype.upper() == "SOLID":
                ET.SubElement(storage, 'DeviceType').text = "SSD"
            elif hddtype.upper() == "ROTATIONAL":
                ET.SubElement(storage, 'DeviceType').text = "HDD"
        except:
            ET.SubElement(storage, 'DeviceType').text = ""
            print("DRIVE TYPE ERROR")
            ERRORS += "DRIVE TYPE ERROR\n"

            # Input Drive Serial Number
        try:
            ET.SubElement(storage, 'SerialNumber').text = SERIALNUM.upper()
        except:
            ET.SubElement(storage, 'SerialNumber').text = ""
            print("DRIVE SERIAL ERROR")
            ERRORS += "DRIVE SERIAL ERROR\n"

        # Input Erasure Method
        ET.SubElement(storage, 'ErasureMethod').text = "NIST 800-88 rev1 Clear"

        # Input Erasure Status
        ET.SubElement(storage, 'ErasureResults').text = "PASS"

        # Extract Drive Capacity
        try:
            if re.search(r"NVMExpress:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"NVMExpress:(.*?)\n\S", input_text, re.DOTALL).group(1)
                capmatch = re.search(r"Capacity: (?P<capacity>\d+(?:\.\d+)?) (TB|GB)", match, re.DOTALL)
            elif re.search(r"SATA/SATA Express:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"SATA/SATA Express:(.*?)\n\S", input_text, re.DOTALL).group(1)
                capmatch = re.search(r"Capacity: (?P<capacity>\d+(?:\.\d+)?) (TB|GB)", match, re.DOTALL)
            elif re.search(r"SATA:(.*?)\n\S", input_text, re.DOTALL) is not None:
                match = re.search(r"SATA:(.*?)\n\S", input_text, re.DOTALL).group(1)
                capmatch = re.search(r"Capacity: (?P<capacity>\d+(?:\.\d+)?) (TB|GB)", match, re.DOTALL)

            if capmatch is not None:
                capacity = capmatch.group("capacity")
                capacity = str(math.floor(float(capacity)))
                unit = capmatch.group(2)
                if unit == "GB":
                    unit_string = " GB"
                elif unit == "TB":
                    unit_string = " TB"
                else:
                    unit_string = ""  # Default if neither "GB" nor "TB" is captured

                ET.SubElement(storage, 'Size').text = capacity + unit_string
            else:
                ET.SubElement(storage, 'Size').text = ""
        except Exception as e:
            ET.SubElement(storage, 'Size').text = ""
            print("DRIVE CAPACITY ERROR")
            ERRORS += "DRIVE CAPACITY ERROR\n"

        # Input Erasure Date
        ERASUREDATE = datetime.datetime.now().strftime('%m/%d/%Y')
        ET.SubElement(storage, 'ErasureDate').text = ERASUREDATE
    # /// Storage

    xml_string = ET.tostring(sysinfo, encoding='utf-8').decode('utf-8')
    xml_dom = minidom.parseString(xml_string)
    xml_pretty_string = xml_dom.toprettyxml(indent="\t")

    return xml_pretty_string

def save_to_output_xml(xml_string, output_file):
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(xml_string)

def log_errors(raw_path):
    global ERRORS
    if ERRORS == "":
        return True
    uid = os.path.basename(raw_path)[:-4]
    errors_path = os.path.join(MOUNT_BASE,APPLE_BASE,"Errors",uid)
    os.makedirs(errors_path, exist_ok=True)
    error_file = os.path.join(errors_path,
                              uid+".log"
                              )
    if os.path.isfile(error_file):
        os.remove(error_file)
    f = open(error_file, "a")
    f.write(ERRORS)
    f.close()
    shutil.copy(raw_path, errors_path)
    return False

def ftp_upload(file_path):
    global ERRORS
    # return true if successful
    file_put_segment = "'set ssl:verify-certificate no; put {0}; exit;'".format(file_path)
    auth = f'{CONFIG["FTP_USER"]},{CONFIG["FTP_PASS"]}'
    
    # Construct FTP command
    ftp_command = [
        'lftp', 
        '-p',
        str(CONFIG["FTP_PORT"]),
        '-u', auth,  # Username and password
        CONFIG["FTP_HOST"],
        '-e',
        file_put_segment
    ]
    cmd = ' '.join(ftp_command)

    # Run FTP upload process
    process = subprocess.run(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        shell=True,
        executable='/bin/bash' #Bash is needed for the <<< redirect
    )
    if process.returncode == 0:
        return True
    else:
        ERRORS += "FTP UPLOAD FAILED\n\n"
        ERRORS += str(process)
        ERRORS += "\n"
        print(f"failed to upload {file_path}")
        print(process)
        return False


def process_RAW_LOGS():
    global ERRORS
    for raw_log_path in RAW_LOGS:
        ERRORS = ""
        print(f"Processing {raw_log_path}")
        basename = os.path.basename(raw_log_path)
        log_xml_name = basename.replace(".txt",".xml")
        
        xml_log_path = clear_collision(log_xml_name)

        with open(raw_log_path, 'r', encoding='utf-8') as file:
            input_text = file.read()

        input_data = parse_input_txt(input_text)
        total_cores = extract_total_cores(input_text)
        xml_string = create_xml(input_data, total_cores, input_text)
        if log_errors(raw_log_path):
            save_to_output_xml(xml_string, xml_log_path)
            if not ftp_upload(xml_log_path):
                log_errors(raw_log_path)
                os.remove(xml_log_path)
            else:
                os.remove(raw_log_path)
            


def main():
    while True:
        try:
            process_RAW_LOGS()
            time.sleep(10)
        except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
                break
        except Exception as e:
            print(f"Error during monitoring: {str(e)}")
            print(str(e))
            time.sleep(10)


if __name__ == "__main__":
    main()

