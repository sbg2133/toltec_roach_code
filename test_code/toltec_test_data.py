import GbE_init as toltec
import casperfpga

iface = "eth0" # Ethernet interface for binding receive socket
firmware = "../firmware/toltec_test_2017_Jul_11_1535.fpg" # Test firmware image
ppc_ip = "192.168.40.55" # IP address of Roach PowerPC
roach = casperfpga.katcp_fpga.KatcpFpga(ppc_ip, timeout=120.)

toltec.upload_firmware(roach, ppc_ip, firmware)
toltec.init_reg(roach)
toltec.stream_UDP(roach, iface, 0, 100)
