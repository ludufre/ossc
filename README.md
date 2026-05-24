Open Source Scan Converter
==============

Open Source Scan Converter is a low-latency video digitizer and scan conversion board designed mainly for connecting retro video game consoles and home computers into modern displays. Please check the [wikipage](http://junkerhq.net/xrgb/index.php?title=OSSC) for more detailed description and latest features.

Requirements for building and debugging firmware
---------------------------------------------------
* Hardware
  * OSSC board
  * USB Blaster compatible JTAG debugger, e.g. Terasic Blaster (for FW installation and debugging)
  * micro SD/SDHC card (for FW update via SD card)

* Software
  * [Altera Quartus II + Cyclone IV support](http://dl.altera.com/?edition=lite) (v 16.1 or higher - free Lite Edition suffices)
  * [RISC-V GNU Compiler Toolchain](https://github.com/riscv/riscv-gnu-toolchain)
  * [Picolibc library for RISC-V](https://github.com/picolibc/picolibc)
  * GCC (or another C compiler) for host architecture (for building a SD card image)
  * Make
  * [iconv](https://en.wikipedia.org/wiki/Iconv) (for building with JP lang menu)


Architecture
------------------------------
* [Reference board schematics](https://github.com/marqs85/ossc_pcb/raw/v1.8/doc/ossc_board.pdf)
* [Reference PCB project](https://github.com/marqs85/ossc_pcb)


SW toolchain build procedure
--------------------------
1. Download, configure, build and install RISC-V toolchain (with RV32EMC support) and Picolibc.

From sources:
~~~~
git clone --recursive https://github.com/riscv/riscv-gnu-toolchain
git clone --recursive https://github.com/picolibc/picolibc
cd riscv-gnu-toolchain
./configure --prefix=/opt/riscv --with-arch=rv32emc --with-abi=ilp32e
sudo make    # sudo needed if installing under default /opt/riscv location
~~~~
On Debian-style Linux distros:
~~~~
sudo apt install gcc-riscv64-unknown-elf binutils-riscv64-unknown-elf picolibc-riscv64-unknown-elf
~~~~

2. Compile custom binary to IHEX converter:
~~~~
gcc tools/bin2hex.c -o tools/bin2hex
~~~~


Building firmware with Docker (no host toolchain install)
---------------------------------------------------------
A pre-configured Docker environment is included for users who want to build the firmware (and host tools) without installing the RISC-V toolchain natively on their host. This path does **not** cover RTL synthesis — Quartus must still be run separately on the host if a new bitstream is required.

Files used: `Dockerfile`, `docker-compose.yml`, `.dockerignore` (all at the repository root). The image is based on Debian Bookworm and works natively on Apple Silicon (linux/arm64) as well as x86_64.

1. Build the image (run once, or after changing the Dockerfile). UID/GID are passed so build artifacts on the bind-mounted directory keep host ownership:
~~~~
UID=$(id -u) GID=$(id -g) docker compose build
~~~~

2. Build the firmware (produces `software/sys_controller/mem_init/flash.bin`):
~~~~
docker compose run --rm build bash -c "touch software/sys_controller_bsp/bsp_timestamp && cd software/sys_controller && make"
~~~~
The `touch bsp_timestamp` step acknowledges that the pre-generated BSP committed to the repository is up to date, skipping the QSYS regeneration that would otherwise require Quartus.

3. Build the host tools:
~~~~
docker compose run --rm build bash -c "cd tools && gcc bin2hex.c -o bin2hex && gcc create_fw_img.c -o create_fw_img"
~~~~

4. Open an interactive shell inside the container for further work:
~~~~
docker compose run --rm build
~~~~

### Obtaining a bitstream (.rbf) without Quartus
If you only need to ship a firmware update with a customized software image, you can re-use the bitstream from an official release. The OSSC firmware `.bin` format (see `tools/create_fw_img.c`) is a 512-byte header followed by the raw RBF, `0xFF` padding, and the software image at offset `0x50000`. Extract the RBF region from any official release (example uses `ossc_1.21-aud.bin`):
~~~~
mkdir -p output_files
dd if=ossc_1.21-aud.bin of=output_files/ossc.rbf bs=1 skip=512 count=327680
~~~~
Then follow the "Generating SD card image" section below to package your custom `flash.bin` with this RBF.

### Toolchain compatibility note
Debian Bookworm's `gcc-riscv64-unknown-elf` 12.2 does not provide a multilib variant matching the modern `rv32emc_zicsr_zifencei` ISA string. The repository uses the equivalent `-misa-spec=2.2 -march=rv32emc -mabi=ilp32e` formulation in `software/sys_controller_bsp/public.mk`, which makes Zicsr/Zifencei implicit in the base ISA and resolves correctly to the link-compatible `rv32em/ilp32e` multilib. This is also accepted by toolchains built from source per the instructions above.

### Limitations
* RTL synthesis (Quartus) is not containerized. Use Quartus on the host or another machine to regenerate `output_files/ossc.rbf`.
* `make rv-reprogram` (JTAG flashing via `system-console` / `jtagconfig`) is not available in the container — it depends on Quartus tooling and USB Blaster passthrough, which is not supported by Docker on macOS. Use the SD card update method for iterating on the software image.


Building RTL (bitstream)
--------------------------
1. Initialize project submodules (once after cloning ossc project or when submoduled have been updated)
~~~~
git submodule update --init --recursive
~~~~
2. Load the project (ossc.qpf) in Quartus
3. Generate QSYS output files (only needed before first compilation or when QSYS structure has been modified)
    * Open Platform Designer (Tools -> Platform Designer)
    * Load platform configuration (sys.qsys)
    * Generate output (Generate -> Generate HDL, Generate)
    * Close Platform Designer
    * Run "patch -p0 <scripts/qsys.patch" to patch generated files to optimize block RAM usage
    * Run "touch software/sys_controller_bsp/bsp_timestamp" to acknowledge QSYS update
4. Generate the FPGA bitstream (Processing -> Start Compilation)
5. Ensure that there are no timing violations by looking into Timing Analyzer report

Building software image
--------------------------
1. Enter software root directory:
~~~~
cd software/sys_controller
~~~~
2. Build SW for target configuration:
~~~~
make [OPTIONS] [TARGET]
~~~~
OPTIONS may include following definitions:
* OSDLANG=JP (Japanese language menu)

TARGET is typically one of the following:
* all (Default target. Compiles an ELF file)
* clean (cleans ELF and intermediate files. Should be invoked every time OPTIONS are changed between compilations, expect with generate_hex where it is done automatically)

3. Optionally test updated SW by directly downloading SW image to flash via JTAG (requires valid FPGA bitstream to be present):
~~~~
make rv-reprogram
~~~~


Installing firmware via JTAG
--------------------------
The bitstream can be either directly programmed into FPGA (volatile method, suitable for quick testing), or into serial flash chip alongside SW image where it is automatically loaded every time FPGA is subsequently powered on (nonvolatile method, suitable for long-term use).

To directly program FPGA, open Programmer in Quartus, select your USB Blaster device, add configuration file (output_files/ossc.sof) and press Start. Download SW image if it not present / up to date in flash.

To program flash, a combined FPGA image must be first generated and converted into JTAG indirect Configuration file (.jic). Open conversion tool ("File->Convert Programming Files") in Quartus, click "Open Conversion Setup Data", select "ossc.cof" and press Generate. Then open Programmer and ensure that "Initiate configuration after programming" and "Unprotect EPCS/EPCQ devices selected for Erase/Program operation" are checked in Tools->Options. Then clear file list, add generated file (output_files/ossc.jic) and press Start after which flash is programmed. Installed/updated firmware is activated when programming finishes (or after power-cycling the board in case of a fresh flash chip).


Generating SD card image
--------------------------
Bitstream file (Altera propiertary format) must be wrapped with custom header structure (including checksums) so that it can be processed reliably on the CPU. This can be done with included helper application which generates an image file which can written on FAT32/exFAT-formatted SD card and subsequently loaded on OSSC:

1. Compile tools/create_fw_img.c
~~~~
cd tools && gcc create_fw_img.c -o create_fw_img
~~~~
2. Generate the firmware image:
~~~~
./create_fw_img <rbf> <sw_image> <offset> <version> [version_suffix]
~~~~
where
* \<rbf\> is RBF format bitstream file (typically ../output_files/ossc.rbf)
* \<sw_image\> is SW image binary (typically ../software/sys_controller/mem_init/flash.bin)
* \<offset\> is relative offset for the SW image binary
* \<version\> is version string (e.g. 1.20)
* \[version_suffix\] is optional max. 8 character suffix name (e.g. "mytest")

The primary firmware has FPGA bitstream at offset 0x0 and SW image at 0x50000 so the command is typically as follows:
~~~~
./create_fw_img ../output_files/ossc.rbf ../software/sys_controller/mem_init/flash.bin 0x50000 1.21 mytest
~~~~
The command creates ossc_\<version\>-\<version_suffix\>.bin which can be copied to fw folder of SD card. A secondary FW (identified by specific key in header) gets automatically installed at flash base address 0x00080000.


Safe testing via secondary firmware slot
----------------------------------------
The flash chip has two firmware slots: primary (`0x00000000`) and secondary (`0x00080000`). The bootloader decides which slot to write to based on the magic key at the start of the firmware header (see `software/sys_controller/src/firmware.c`):

* Magic `"OSSC"` → written to primary, replacing the running firmware
* Magic `"OSS2"` → written to secondary, **primary left intact**

A secondary-slot image is dormant until activated through the **Settings opt → Launch 2nd FW** menu entry, which triggers an FPGA reconfiguration from `0x00080000`. A simple power cycle always falls back to the primary slot. This makes the secondary slot a safe target when testing custom builds without risking a brick — if the build hangs or misbehaves, just power-cycle.

`create_fw_img` always writes the `"OSSC"` magic. To produce an `"OSS2"`-keyed variant from an already-generated firmware image, use the included helper (no rebuild required — it only patches byte 3 of the header and recomputes the header CRC; the data section is left untouched):

~~~~
python3 tools/make_secondary.py tools/ossc_<version>-<suffix>.bin
~~~~

This writes `tools/ossc_<version>-<suffix>-sec.bin` alongside the original. Copy it to the `fw/` folder of the SD card just like any other firmware image. When the bootloader's update menu shows the version string, it appends ` (sec)` so you can visually confirm before committing the flash:

~~~~
v1.21-mytest (sec)
Update? 1=Y, 2=N
~~~~

Recommended workflow for testing custom builds:

1. Build firmware (`make` in `software/sys_controller/`)
2. Package it (`create_fw_img ... 1.21 mytest`) → produces `ossc_1.21-mytest.bin`
3. Patch to secondary (`tools/make_secondary.py tools/ossc_1.21-mytest.bin`) → produces `ossc_1.21-mytest-sec.bin`
4. Copy the `-sec.bin` to SD card `fw/` folder
5. Install via menu — confirm the `(sec)` suffix in the prompt before pressing `1`
6. After install completes, the board reboots running the unchanged primary firmware
7. Activate the new build via **Settings opt → Launch 2nd FW**
8. To roll back: power-cycle (boot default is primary), or invoke **Launch 2nd FW** again to toggle


Debugging
--------------------------
1. Rebuild the software in debug mode:
~~~~
make clean && make APP_CFLAGS_DEBUG_LEVEL="-DDEBUG"
~~~~

2. Flash SW image via JTAG and open terminal for UART
~~~~
make rv-reprogram && nios2-terminal
~~~~
Remember to close nios2-terminal after debug session, otherwise any JTAG transactions will hang/fail.


License
---------------------------------------------------
[GPL3](LICENSE)