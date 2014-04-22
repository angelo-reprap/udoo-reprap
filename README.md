Download (Files) -> un "ZIP" -> Win32DiskImage (32GB SD-Cart) write -> SD-Card plug in UDOO Quad slot and Power on. 
If you are in the same LAN, open Browser http://udoo-reprap and the registration of OpenMediaVault must have on the screen. 
Openmediavault http://udoo-reprap user= admin password = reprap 
OctoPrint http://udoo-reprap:5000 user = udoo password = reprap 
Webmin https://udoo-reprap:10000 user = root password = reprap 
VNC-Viewer-5.1.0-Windows-64bit vnc password = reprap 
putty udoo-reprap Port:22 user = root password = reprap 
To install the Services is your Job :-) 

CAUTION: 
No support of LCD + touch, no HDMI, no webcam support and SATA could run, but not tested. 
Cura and Slic3r only on commandline - 
OpenGL GLX is not because the GPU driver module-core does not yet work on armhf. 
http://forums.reprap.org/read.php?336,340416