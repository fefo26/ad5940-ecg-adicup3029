# ECG on EVAL-ADICUP3029 + EVAL-AD5940BIOZ

Firmware, test firmwares and a live viewer to get an ECG out of the EVAL-AD5940BIOZ shield
(AD5940 + AD8233) on an EVAL-ADICUP3029. The AD8233 output is sampled by the AD5940 ADC at 250 SPS
and printed on the UART in mV; `ecg_view.py` plots it.

| Path | Content |
|---|---|
| `firmware/` | The applications and the board support for the ADuCM3029. |
| `Makefile` | Downloads the toolchain and the vendor code, builds, flashes, starts the viewer. |
| `ecg_view.py` | Live viewer for Linux, Windows and macOS. |
| `TESTLOG.md` | The bench tests that led to this setup, with the measured values. |

The repository holds only its own sources. The Analog Devices AD5940 library and device pack are
downloaded by the Makefile and stay under their own licences.

## Hardware setup

Settings marked *measured* were confirmed by the firmware self check or a test firmware; the others
come from the EVAL-AD5940BIOZ schematic published by Analog Devices.

| Jumper | Setting | Why |
|---|---|---|
| P10 | cap fitted so that pin 2 (AD8233 supply) is powered; 1-2 takes it from AVDD | Without it the AD8233 is only back-powered through its control pins (about 2 V). *Measured*: the self check must report a pull-up rail of 2.9 V or more. |
| P13 | 2-3 (FR to ground) | Fast restore off. With FR high or floating the AD8233 keeps re-triggering fast restore: regular pulses every 0.175 s multiples and no ECG band. *Measured*. |
| P16 | 1-2 (+IN pulled up to the bias net) | Input bias. |
| P17 | 1-2, same as P16 | Both inputs must be biased the same way. With -IN pulled down a DC offset above the AD8233 range appears and the output sticks at a rail. *Measured*. |
| JP7 | 3-5 (bias net = AD8233 supply), the default printed on the schematic | Pull-up level of the inputs. |
| JP5, JP6 | open | A cap ties the S- or S+ lead to the bias net or to ground. |
| P20 | optional | Connects the AD8233 leads-off output to GP4, reported by the firmware. |
| JP3 | C (reset from the shield GPIO) | Lets the MCU reset the AD5940 (A3). Not verified. |

Buttons: URST restarts the MCU firmware; ARST resets only the AD5940 and leaves the stream dead
until the next URST.

### Probes

Verified with the `LeadId` firmware on the three probe cable:

| Probe | Lead | Role | Body position |
|---|---|---|---|
| red | F+ | ECG input + | left wrist or arm |
| blue | S- | ECG input - | right wrist or arm |
| black | F- | right leg drive (reference) | ankle or leg |

The S+ lead is not used. Swapping red and blue only inverts the trace.

### Power

Run the laptop on battery and plug the board directly into it: no charger, no dock. On mains the
same setup shows only noise (about 22 mV rms at the output, no heartbeat); on battery the R peaks
are about 160 mV. Each lead has 300 kOhm in series plus the pad, into inputs biased through
10 MOhm, so common-mode interference from a mains-connected ground is rejected poorly. With mains
power a USB isolator is needed.

After connecting the probes wait 10 to 20 s: with fast restore off the amplifier settles slowly.

## Build

`make` downloads what it needs on the first run and then builds. Nothing else has to be installed
by hand apart from the tools below.

| Component | Source | Size |
|---|---|---|
| Arm GNU toolchain 13.2.rel1 | developer.arm.com (Linux x86_64 tar.xz, Windows zip) | 180 MB / 365 MB |
| ADuCM302x_DFP 3.2.0 device pack | download.analog.com (Analog Devices licence applies) | 37 MB |
| CMSIS 5.4.0 core headers | github.com/ARM-software/CMSIS_5 | 5 files |
| AD5940 library (ad5940lib, commit d4c2ba0) | github.com/analogdevicesinc/ad5940lib | 2 files |

They go to `.deps/` (`DEPS=` changes the place), which is not tracked by git.

### Windows quick start

In a Command Prompt or PowerShell window, in the project folder:

```
install.bat               # GNU make and Python 3.14 with winget, pyserial, then "make deps"
```

Then open a new terminal (so that the newly installed tools are on the PATH) and use `make`,
`make flash DAPLINK=E:` and `make view` as below. `install.bat` skips what is already installed.
It has not been run on a Windows machine yet.

### Tools


- Linux: GNU make, curl, tar, unzip.
- Windows: GNU make for Windows (winget package `ezwinports.make`); curl and tar are the ones
  shipped with Windows 10 or later. The Makefile runs its commands with `cmd.exe`. The Windows
  side follows the same rules as the Linux one but has not been run on a Windows machine yet.

```
make deps                 # only download
make                      # firmware/EcgStream.c -> build/EcgStream/EcgStream.hex
make APP=LeadId           # another application, see the table below
make CROSS=arm-none-eabi- # use a toolchain already in the PATH
make clean
```

## Flash and run

```
make flash                # Linux: copies to /run/media/$USER/DAPLINK, then press URST
make flash DAPLINK=E:     # Windows: give the drive letter of the DAPLINK drive
make flash APP=LeadId     # flash another application
```

The on-board DAPLink does not reset the target after programming, so press URST. The serial port
is 230400 baud; only one program can read it at a time.

## Live viewer

`ecg_view.py` plots the stream in a scrolling window. It is one Python file that runs unchanged on
Linux, Windows and macOS; it needs Python 3 with Tk (part of the python.org installer on Windows,
`python3-tk` on Debian/Ubuntu) and pyserial. On Windows the Makefile starts it with `py -3`.

```
make view                 # installs pyserial if missing, then starts the viewer
make view PORT=COM5       # or PORT=/dev/ttyACM1 to choose the port
python ecg_view.py --list # USB serial ports, the board is marked
python ecg_view.py --seconds 5 --log serial.log
```

Without a port the viewer finds the board by the USB id of its DAPLink (0d28:0204), waits if it is
not plugged in and reconnects after a replug. Space pauses, `q` quits. The bottom line shows the
connection and, for a few seconds, the last status line of the firmware. It was run on Linux with
the board; on Windows it has not been run yet.

Output: one sample per line in mV; lines starting with `#` are status. At every reset the firmware
prints a self check:

```
# AD8233 input pull-up rail: 2.94 V
# lead F+ (IN+, red): IN+ 1.08 V, IN- 0.96 V: connected
```

## Applications

Select with `APP=`; the sources are in `firmware/`.

| APP | Purpose |
|---|---|
| `EcgStream` (default) | ECG stream: AD8233 output at 250 SPS, 50 Hz removed by a 5 sample average, FIFO polled (no sequencer, no interrupt). |
| `EcgChainTest` | Reference test without leads: the AD5940 DAC applies a synthetic beat (1 mV R wave, 0.2 mV T wave) at the AD8233 inputs. Expected about 220 mV and 44 mV at the output, noise 1 to 2 mV rms. |
| `LeadId` | Clip two probe tips together (off the body): prints which two leads are shorted. |
| `EcgPathDiag` | DC voltages of the nodes between the electrodes and the ADC. |

`firmware/board_adicup3029.c` is the board support shared by all of them: clock, UART at 230400
baud, SPI and the pins of the AD5940. The UART receiver is not used.

## Troubleshooting

| Symptom | Cause |
|---|---|
| The Analog Devices ECG example prints nothing after the first lines | Its ADICUP3029 port enables the UART receive interrupt without a handler: the first byte received from the host hangs the MCU. This firmware leaves that interrupt off. |
| Constant 65532 or output at a rail, rail below 2.9 V in the self check | P10: the AD8233 is not powered. |
| Output at a rail with the probes on, inputs far apart in the self check | P17 not like P16, or a probe is off. |
| Regular spikes on a fixed time grid, flat baseline, no heartbeat | P13: fast restore enabled. |
| Only noise, no rhythm, probes connected | Laptop on mains: use battery and a direct USB connection. |
| Lead reported OPEN | Positive probe on S+ instead of F+ is fine (both are routed); otherwise check the pad and the cable. |
