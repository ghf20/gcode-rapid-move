# G-Code Rapid Move Converter & Simulator

**Description**  
This Python script simulates and converts G-code files from Fusion 360 (free version). It allows you to:

- Simulate G-code execution to track machine state (X, Y, Z, feed, spindle, and more).  
- Estimate total run time for your program.  
- Convert safe G1 feed moves to G0 rapid moves to optimize CNC machining paths.  
- Perform dry-run previews before modifying files.  

It is ideal for testing G-code conversions and estimating CNC job durations without risking your machine or material.

---

## Features

- **G-code Simulation**: Tracks machine state and feed rates for accurate estimation.  
- **Rapid Conversion**: Converts feed moves to rapids when above a safe Z height.  
- **Time Estimation**: Computes estimated run time based on feed and rapid rates.  
- **Dry-run Mode**: Preview changes before saving them.  
- **Conservative & Aggressive Modes**: Control how aggressively moves are converted.  

---

### Usage

```bash
python script.py <input_file> [output_file] [options]
```
Options

- --z-safe=<height> : Z height for safe rapid moves (default: 17.0 mm)

- --aggressive : Convert all moves at or above safe Z, not just conservative ones

- --rapid-rate=<rate> : Rapid speed for G0 time estimation (default: 5000 mm/min)

- --dry-run : Preview changes without modifying the file

### Examples
```bash
# Dry-run preview
python script.py input.nc --dry-run

# Convert with custom safe Z and rapid rate
python script.py input.nc output.nc --z-safe=16.5 --rapid-rate=8000
```
---

## Output

- Conversion statistics (total lines, number of G1 -> G0 conversions).

- Estimated total run time (hours, minutes, seconds).

- Optional output file with converted G-code (unless --dry-run is used).

## Viewing G-code Paths

To visualize the CNC paths, you can use any of these free or online NC viewers:

- NC Viewer - browser-based, easy to use.

- CAMotics - free desktop simulator for Windows, macOS, Linux.

## Disclaimer

 **Use at Your Own Risk!**

- This script simulates G-code and estimates run time, but it cannot guarantee safe operation on your CNC machine.

- Always verify and simulate the output G-code before running it on your machine.

- Incorrect G-code can cause damage to your machine, tools, or workpiece.

- You are solely responsible for any consequences of using this script.

Requirements

- Python 3.7 or higher