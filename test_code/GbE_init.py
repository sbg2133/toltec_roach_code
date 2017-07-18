import numpy as np
import socket as sock
import struct
import select
import sys
import time

### This script generates Roach2 test packets. Use with TolTEC test firmware.
### author = Sam Gordon (sbgordo1@asu.edu)

### Global parameters ###

# IP address corresponding to iface
dest_ip  = 192*(2**24) + 168*(2**16) + 50*(2**8) + 1
dest_port= 60001 # Port number used with dest_ip

# source IP address of Roach packets, hardcoded in firmware
# (source port is hardcoded as: 60000)
roach_saddr = "192.168.40.71"

data_len = 8192 # Data size in bytes, hardcoded in firmware
header_len = 42 # Header size in bytes, hardcoded in firmwmare
buf_size = data_len + header_len

f_fpga = 256.0e6 # FPGA clock frequency, 256 MHz

# Number of data accumulations per output sample.
# Used to set output packet data rate.
accum_len = 2**19

data_rate = f_fpga/accum_len # Output packet data rate

### Upload firmware
def upload_firmware(roach, ppc_ip, firmware_file):
    print 'Connecting...'
    katcp_port=7147
    t1 = time.time()
    timeout = 10
    while not roach.is_connected():
       if (time.time() - t1) > timeout:
           raise Exception("Connection timeout to roach")
    time.sleep(0.1)
    if (roach.is_connected() == True):
        print 'Connected to the FPGA '
        roach.upload_to_ram_and_program(str(firmware_file))
    else:
        print 'Not connected to the FPGA'
    time.sleep(2)
    print 'Connection established to', ppc_ip
    print 'Uploaded', firmware_file
    return

### Initialize GbE parameters
def init_reg(roach):
    roach.write_int('GbE_tx_destip', dest_ip)
    roach.write_int('GbE_tx_destport', dest_port)
    roach.write_int('sync_accum_len', accum_len - 1)
    roach.write_int('GbE_tx_rst',0)
    roach.write_int('GbE_tx_rst',1)
    roach.write_int('GbE_tx_rst',0)
    roach.write_int('start', 1)
    roach.write_int('sync_accum_reset', 0)
    roach.write_int('sync_accum_reset', 1)
    return

### Create a socket for receiving UDP data,
# bind to eth_iface (raw socket is used here, could be datagram).
def init_socket(eth_iface):
    sock_fd = sock.socket(sock.AF_PACKET, sock.SOCK_RAW, 3)
    sock_fd.setsockopt(sock.SOL_SOCKET, sock.SO_RCVBUF, buf_size)
    sock_fd.bind((eth_iface, 3))
    return sock_fd

### sock = socket file descriptor
def wait_for_data(sock_fd):
    read, write, error = select.select([sock_fd], [], [])
    while (1):
        for s in read:
            packet = s.recv(buf_size)
            if len(packet) == buf_size:
                return packet
            else:
		pass
    return

### Stream set number of packets (Npackets) on Eth interface, iface.
### Prints header and data info for a single channel (0 < chan < 1016)
def stream_UDP(roach, iface, chan, Npackets):
    sock_fd = init_socket(iface)
    roach.write_int('GbE_pps_start', 0)
    roach.write_int('GbE_pps_start', 1)
    count = 0
    # previous_idx = np.zeros(1)
    while count < Npackets:
        packet_data = wait_for_data(sock_fd)
        header = packet_data[:header_len]
        saddr = np.fromstring(header[26:30], dtype = "<I")
        saddr = sock.inet_ntoa(saddr) # source addr

        if (saddr != roach_saddr):
            continue

        ### Print header info ###
        daddr = np.fromstring(header[30:34], dtype = "<I")
        daddr = sock.inet_ntoa(daddr) # dest addr
        smac = np.fromstring(header[6:12], dtype = "<B")
        src = np.fromstring(header[34:36], dtype = ">H")[0]
        dst = np.fromstring(header[36:38], dtype = ">H")[0]

        ### Parse packet data ###
        data = np.fromstring(packet_data[header_len:], dtype = '<i').astype('float')
        roach_checksum = (np.fromstring(packet_data[-16:-12],dtype = '>I'))

        # seconds elapsed since 'pps_start'
        sec_ts = (np.fromstring(packet_data[-12:-8],dtype = '>I'))
        # milliseconds since last packet
        fine_ts = np.round((np.fromstring(packet_data[-8:-4],dtype = '>I').astype('float')/f_fpga)*1.0e3,3)
        # raw packet count since 'pps_start'
        packet_count = (np.fromstring(packet_data[-4:],dtype = '>I'))
        ### Check for packet index errors ###
        # if count > 0:
	#    if (packet_count - previous_idx != 1):
    	#	print "Packet index error"
  	#	break
        if (chan % 2) > 0:
	    I = data[1024 + ((chan - 1) / 2)]
	    Q = data[1536 + ((chan - 1) /2)]
        else:
	    I = data[0 + (chan/21)]
	    Q = data[512 + (chan/2)]
        phase = np.degrees(np.arctan2([Q],[I]))
	print
	print "Roach chan =", chan
        print "src MAC = %x:%x:%x:%x:%x:%x" % struct.unpack("BBBBBB", smac)
	print "src IP : src port =", saddr,":", src
	print "dst IP : dst port  =", daddr,":", dst
	print "Roach chksum =", roach_checksum[0]
	print "PPS count =", sec_ts[0]
	print "Packet count =", packet_count[0]
        print "I (unscaled) =", I
        print "Q (unscaled) =", Q
        count += 1
	# previous_idx = packet_count
    sock_fd.close()
    return
