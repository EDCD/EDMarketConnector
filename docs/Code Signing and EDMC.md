# Code Signing
As of version 5.10.2, we now sign our releases of the EDMC installer. Code signing is a method where we can digitally sign our executables and scripts to confirm the software has not been altered since it was signed. Due to how the code signing options we have available work, the automatically built EXE must be downloaded to the developer's machine, signed, and uploaded back to GitHub. This is the only modification that has been made. 

This code signing allows us a greater level of confidence in distributions of EDMC, gives various AntiVirus products greater confidence in the legitimacy of the tool (reducing the number of false positive detections), and also assists in ensuring our code is not modified from the point of signing onward.

## How does Code Signing impact EDMC?
Code Signing for the main EDMC releases will not impact the average user's experience with EDMC installers. Installations from the source files are not impacted by this change. 

For users who use signed installers, the normal Windows UAC authentication prompt will include additional information about the signed code. A signed release will look something like this:

![image](https://github.com/EDCD/EDMarketConnector/assets/26337384/f90a7ae4-a594-4fdf-9d1d-356ab381d6b4)

Users who inspect the installer exe file will also be able to see a digital signature in Windows Explorer:

![image](https://github.com/EDCD/EDMarketConnector/assets/26337384/de72dc25-3f97-41bf-bb88-c07ded5b19d6)

## Opting Out
Some users may be uncomfortable using a signed release and prefer to use unsigned releases, which are pure automatic builds. We absolutely understand these concerns! These WILL BE MADE AVAILABLE on the GitHub release page for every release going forward. This will require manual updates and will not be distributed through the WinSparkle update system.
