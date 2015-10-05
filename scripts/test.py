#!/bin/env python
# Samuel Jero <sjero@purdue.edu>
# Actual strategy test routines
import manage_vms as mv
import os
import sys
import subprocess
import time
from datetime import datetime

system_home = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
lib_path = os.path.abspath(os.path.join(system_home, 'scripts','libs'))
config_path = os.path.abspath(os.path.join(system_home, 'config'))
mininet_config_path = os.path.abspath(os.path.join(system_home, 'mininet_scripts'))
sys.path.insert(1,lib_path)
sys.path.insert(0,config_path)
import spur
import config

class SDNTester:
	def __init__(self,mininet, controllers, log):
		assert(isinstance(mininet, (list,tuple)) and isinstance(controllers, (list,tuple)) and len(mininet) == 1)
		self.mininet = mininet
		self.controllers = controllers
		self.log = log
		self.testnum = 1

	def doTest(self,test_script, strategy):
		result = True
		self.log.write("##############################Starting Test " + str(self.testnum) + "###################################\n")
		self.log.write(str(datetime.today()) + "\n")
		#Create Address/Port strings
		controlleraddrs = list()
		proxyaddrs = list()
		proxyports = list()
		for c in self.controllers:
			controlleraddrs.append(mv.vm2ip(c) + ":" + str(config.controller_port))
			proxyaddrs.append(config.proxy_addr + ":" + str(config.proxy_base_port + c))
			proxyports.append(str(config.proxy_base_port + c))

		#Start Proxy
		cmd = config.proxy_path + " -p " + str(config.proxy_com_port + self.mininet[0])
		for c in range(0,len(controlleraddrs)):
			cmd = cmd + " -c " +  proxyports[c] + ":" + controlleraddrs[c]
		self.log.write("Proxy CMD: " + cmd + "\n")
		self.log.write("********* Proxy output ********\n")
		self.log.flush()
		try:
			proxy = subprocess.Popen(cmd, shell = True, stdout = self.log, stderr = subprocess.STDOUT)
		except Exception as e:
			print e
			self.log.write("Exception: " + str(e) + "\n")
			self.log.flush()
			return False
		if(self._waitListening("localhost",config.proxy_com_port + self.mininet[0],60)==False):
			self.log.write("Proxy failed to start after 60 seconds\n")
			self.log.flush()
			return False

		#Veriflow
		veriflow = None
		if config.veriflow_enabled:
			assert(len(controllers)==1)
			vf_port = config.veriflow_base_port + self.controllers[0]
			topo_file = config.veriflow_topo_path + os.path.splitext(os.path.basename(test_script.format(controllers="").strip()))[0] + ".vft"
			cmd = config.veriflow_path + " " + str(vf_port) + " 127.0.0.1  " + proxyports[0] + " " + topo_file
			self.log.write("Veriflow CMD: " + cmd + "\n")
			self.log.flush()
			proxyaddrs = list()
			proxyaddrs.append(config.proxy_addr + ":" + str(vf_port))
			try:
				veriflow = subprocess.Popen(cmd, shell = True, stdout = self.log, stderr = subprocess.STDOUT)
			except Exception as e:
				print e
				self.log.write("Exception: " + str(e) + "\n")
				self.log.flush()
				return False
			if(self._waitListening("localhost",config.veriflow_base_port + self.controllers[0],60)==False):
				self.log.write("Veriflow failed to start after 60 seconds\n")
				self.log.flush()
				return False

		#Send Proxy Strategy
		for l in strategy:
			cmd = config.ctl_path + " -p " + str(config.proxy_com_port + self.mininet[0]) + " localhost \"" + l.format(controllers=proxyports) + "\""
			self.log.write("Strategy CMD: " + cmd + "\n")
			self.log.flush()
			try:
				com = subprocess.Popen(cmd, shell = True , stdout = log, stderr = subprocess.STDOUT)
				com.wait()
			except Exception as e:
				print e
				self.log.write("Exception: " + str(e) + "\n")
				self.log.flush()
				result = False


		#Start Controllers
		for c in self.controllers:
			shell = spur.SshShell(hostname=mv.vm2ip(c), username = config.controller_user, missing_host_key=spur.ssh.MissingHostKey.accept)
			res = shell.run(["/bin/bash","-i" ,"-c", config.controller_start_cmd])
			self.log.write("Starting Controller (" + mv.vm2ip(c) + ")... " + res.output + "\n")
			self.log.flush()
		for c in self.controllers:
			if(self._waitListening(mv.vm2ip(c),config.controller_port,60)==False):
				self.log.write("Controller %s failed to start after %d seconds" % (mv.vm2ip(c),60))
				self.log.flush()
				result = False

		#Do Test
		res = None
		proc = None
		m = mininet[0]
		shell = spur.SshShell(hostname=mv.vm2ip(m), username = config.mininet_user, missing_host_key=spur.ssh.MissingHostKey.accept)
		self.log.write("Starting Test: " + test_script.format(controllers=" ".join(proxyaddrs)) + "\n")
		self.log.flush()
		try:
			proc = shell.run(["/bin/bash","-i" ,"-c", test_script.format(controllers=" ".join(proxyaddrs))])
			res = eval(proc.output)
		except Exception as e:
			print e
			self.log.write("Exception: " + str(e) + "\n")
			self.log.flush()

		#Evaluate Results
		if  isinstance(res, (list,tuple)):
			for r in res:
				if r == False:
					result = False
		else:
			result = False
		
		#Stop Controllers
		for c in self.controllers:
			shell = spur.SshShell(hostname=mv.vm2ip(c), username = config.controller_user, missing_host_key=spur.ssh.MissingHostKey.accept)
			res = shell.run(["/bin/bash","-i" ,"-c", config.controller_stop_cmd])

		#Stop Proxy
		proxy.terminate()

		#Stop Veriflow
		if config.veriflow_enabled:
			veriflow.send_signal(2)

		#Cleanup Any Mininet Remnants
		shell = spur.SshShell(hostname=mv.vm2ip(m), username = config.mininet_user, missing_host_key=spur.ssh.MissingHostKey.accept)
		res = shell.run(["/bin/bash","-i" ,"-c", config.mininet_cleanup_cmd])
	
		#Log
		self.log.flush()
		self.log.write("*****************\n")
		self.log.write("********* Test Script output ********\n")
		if proc:
			self.log.write(proc.stderr_output)
		self.log.write("*****************\n")
		self.log.write("Test Result: " + str(result) + "\n")
		self.log.write(str(datetime.today()) + "\n")
		self.log.write("##############################Ending Test " + str(self.testnum) + "###################################\n")
		self.log.flush()
		self.testnum+=1
		return result


	def startVms(self):
		for c in self.controllers:
			mv.startvm(c)
		for m in self.mininet:
			mv.startvm(m)
		for c in self.controllers:
			if(self._waitListening(mv.vm2ip(c),22,60,True)==False):
				print "Error: Controller %d not started!" % (c)
		for m in self.mininet:
			if(self._waitListening(mv.vm2ip(m),22,60,True)==False):
				print "Error: Mininet %d not started!" % (c)
			else:
				if config.mininet_replace_scripts:
					os.system("scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -r %s/* %s@%s:~\n" % (mininet_config_path, config.mininet_user, mv.vm2ip(m)))

	def stopVms(self):
		for c in self.controllers:
			mv.stopvm(c)
		for m in self.mininet:
			mv.stopvm(m)

	def _waitListening(self,host='127.0.0.1', port=80, timeout=None, output=False):
		"""Wait until server is listening on port.
		returns True if server is listening"""
		cmd = ('echo A | telnet -e A %s %s' % ( host, port ))
		start = time.time()
		result = ""
		try:
			result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
		except subprocess.CalledProcessError as e:
			pass
		while 'Connected' not in result:
			if 'No route' in result:
				return False
			if timeout and time.time() >= start + timeout:
				print 'could not connect to %s on port %d' % (host, port )
				return False
			if output:
				print 'waiting for ' + host + ' to listen on port ' + str(port)
			time.sleep(0.5)
			try:
				result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
			except subprocess.CalledProcessError as e:
				pass
		if output:
			print host + " is listening on " + str(port)
			return True

if __name__ == "__main__":
	print "Running demo..."
	tester = SDNTester([1],[2],sys.stdout)
	print tester.doTest("/root/test1.py {controllers}", ["d"])