#!/usr/bin/env python3
"""
G-code simulator and converter for Fusion 360 free version.
Tests conversions before applying them, and estimates run time.

Rapid Gcode © 2025 by George Fraser is licensed under CC BY-NC 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by-nc/4.0/ 
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple

@dataclass
class MachineState:
    """Tracks the complete state of the CNC machine."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    current_g: Optional[int] = None  # Modal G command (0, 1, 2, 3)
    feed_rate: Optional[float] = None
    spindle_speed: Optional[int] = None
    absolute_mode: bool = True  # G90/G91
    units_mm: bool = True  # G21/G20
    plane: str = 'XY'  # G17/G18/G19
    work_coordinate: str = 'G54'
    total_time_seconds: float = 0.0  # NEW: Tracks total run time
    
    def copy(self):
        """Create a copy of the current state."""
        return MachineState(
            x=self.x, y=self.y, z=self.z,
            current_g=self.current_g,
            feed_rate=self.feed_rate,
            spindle_speed=self.spindle_speed,
            absolute_mode=self.absolute_mode,
            units_mm=self.units_mm,
            plane=self.plane,
            work_coordinate=self.work_coordinate,
            total_time_seconds=self.total_time_seconds
        )

class GCodeSimulator:
    """Simulates G-code execution to track machine state."""
    
    # Set default rapid rate (5000 mm/min)
    def __init__(self, rapid_rate: float = 5000.0): 
        self.state = MachineState()
        self.move_history = []
        self.rapid_traverse_rate = rapid_rate # Used for G0 time estimation
        
    def parse_line(self, line: str) -> dict:
        """Parse a G-code line into components."""
        line = line.strip()
        
        # Remove comments
        line = re.sub(r'\(.*?\)', '', line)
        line = re.sub(r';.*$', '', line)
        line = line.strip()
        
        if not line:
            return {'type': 'empty'}
        
        result = {'type': 'command', 'original': line}
        
        # Extract G command
        g_match = re.search(r'G0*(\d+)', line, re.IGNORECASE)
        if g_match:
            result['G'] = int(g_match.group(1))
        
        # Extract M command
        m_match = re.search(r'M(\d+)', line, re.IGNORECASE)
        if m_match:
            result['M'] = int(m_match.group(1))
        
        # Extract coordinates
        for axis in ['X', 'Y', 'Z', 'I', 'J', 'K', 'R']:
            match = re.search(rf'{axis}([-+]?\d*\.?\d+)', line, re.IGNORECASE)
            if match:
                result[axis] = float(match.group(1))
        
        # Extract feed rate
        f_match = re.search(r'F([-+]?\d*\.?\d+)', line, re.IGNORECASE)
        if f_match:
            result['F'] = float(f_match.group(1))
        
        # Extract spindle speed
        s_match = re.search(r'S(\d+)', line, re.IGNORECASE)
        if s_match:
            result['S'] = int(s_match.group(1))
        
        return result
    
    def execute_line(self, line: str) -> Tuple[MachineState, Optional[dict]]:
        """Execute a line and return new state and move info."""
        parsed = self.parse_line(line)
        
        if 'G' in parsed and parsed['G'] == 10 and 'Z' in parsed:
            self.state.z = parsed['Z']  # Set current Z to probe zero
            return self.state, None
        
        old_state = self.state.copy()
        
        # Update modal settings
        if 'G' in parsed:
            g = parsed['G']
            if g in [0, 1, 2, 3]:  # Motion commands
                self.state.current_g = g
            elif g == 90:
                self.state.absolute_mode = True
            elif g == 91:
                self.state.absolute_mode = False
            elif g == 21:
                self.state.units_mm = True
            elif g == 20:
                self.state.units_mm = False
            elif g == 17:
                self.state.plane = 'XY'
            elif g == 18:
                self.state.plane = 'XZ'
            elif g == 19:
                self.state.plane = 'YZ'
            elif g in [54, 55, 56, 57, 58, 59]:
                self.state.work_coordinate = f'G{g}'
        
        # Update feed rate
        if 'F' in parsed:
            self.state.feed_rate = parsed['F']
        
        # Update spindle speed
        if 'S' in parsed:
            self.state.spindle_speed = parsed['S']
        
        # Execute motion
        move_info = None
        if self.state.current_g in [0, 1, 2, 3]:
            # Calculate new position
            new_x = self.state.x
            new_y = self.state.y
            new_z = self.state.z
            
            if 'X' in parsed:
                new_x = parsed['X'] if self.state.absolute_mode else self.state.x + parsed['X']
            if 'Y' in parsed:
                new_y = parsed['Y'] if self.state.absolute_mode else self.state.y + parsed['Y']
            if 'Z' in parsed:
                new_z = parsed['Z'] if self.state.absolute_mode else self.state.z + parsed['Z']
            
            # Check if this is actually a move
            if new_x != self.state.x or new_y != self.state.y or new_z != self.state.z:
                
                # Calculate 3D Distance (Distance Formula)
                dx = new_x - self.state.x
                dy = new_y - self.state.y
                dz = new_z - self.state.z
                distance = (dx**2 + dy**2 + dz**2)**0.5
                
                # Determine Rate and Calculate Time
                rate_per_minute = 0.0
                
                if self.state.current_g == 0:
                    # Rapid move uses the fixed rapid rate
                    rate_per_minute = self.rapid_traverse_rate
                elif self.state.current_g in [1, 2, 3]:
                    # Feed move uses the F rate, or defaults if missing
                    # Use a sensible default (e.g., 1.0 mm/min) to avoid division by zero if F is unset
                    rate_per_minute = self.state.feed_rate if self.state.feed_rate is not None else 1.0 
                
                time_in_minutes = distance / rate_per_minute if rate_per_minute > 0 else 0.0
                time_in_seconds = time_in_minutes * 60.0
                
                # Update Machine State
                self.state.total_time_seconds += time_in_seconds
                
                move_info = {
                    'type': 'rapid' if self.state.current_g == 0 else 'feed',
                    'from': (self.state.x, self.state.y, self.state.z),
                    'to': (new_x, new_y, new_z),
                    'feed_rate': self.state.feed_rate if self.state.current_g != 0 else None,
                    'distance': distance,
                    'time_s': time_in_seconds
                }
                
                self.state.x = new_x
                self.state.y = new_y
                self.state.z = new_z
                
                self.move_history.append(move_info)
        
        return self.state, move_info

class GCodeConverter:
    """Converts G1 travel moves to G0 rapids."""
    
    def __init__(self, z_safe: float = 17.0, conservative: bool = True, rapid_rate: float = 5000.0):
        self.z_safe = z_safe
        self.conservative = conservative
        self.simulator = GCodeSimulator(rapid_rate=rapid_rate)
        
    def should_convert_to_rapid(self, parsed: dict, state: MachineState) -> bool:
        """Convert G1 to G0 only if fully above safe Z."""
        current_g = parsed.get('G', state.current_g)
        if current_g != 1:
            return False

        # No coordinates? Not a move
        if not any(k in parsed for k in ['X', 'Y', 'Z']):
            return False

        # Determine target Z
        target_z = state.z
        if 'Z' in parsed:
            target_z = parsed['Z'] if state.absolute_mode else state.z + parsed['Z']

        # Check both current Z and target Z
        if state.z >= self.z_safe and target_z >= self.z_safe:
            # XY moves only if already at safe Z
            if self.conservative and 'Z' not in parsed:
                return True
            # Z moves upward only
            if 'Z' in parsed and target_z >= state.z:
                return True
            # Aggressive mode converts any safe-Z move
            if not self.conservative:
                return True

        return False  # Below safe Z
        
    def convert_line(self, line: str, state: MachineState) -> Tuple[str, bool]:
        """Convert a single line if appropriate. Returns (new_line, was_converted)."""
        stripped = line.strip()
        parsed = self.simulator.parse_line(stripped)
        
        if parsed['type'] == 'empty':
            return line, False
        
        # Check if we should convert
        if not self.should_convert_to_rapid(parsed, state):
            return line, False
        
        # Need to convert this G1 move to G0
        
        # Check if line already has G command
        has_g_command = re.search(r'\bG0*\d+', stripped, re.IGNORECASE)
        
        if has_g_command:
            # Replace existing G1 with G0
            new_line = re.sub(r'\bG0*1\b', 'G0', stripped, flags=re.IGNORECASE)
        else:
            # No G command - this is modal G1, need to add G0
            new_line = 'G0 ' + stripped
        
        # Remove feed rate from G0 moves (rapids don't use feed rates)
        new_line = re.sub(r'\s*F[-+]?\d*\.?\d+', '', new_line, flags=re.IGNORECASE)
        
        # Preserve original line ending style
        if line.endswith('\n'):
            new_line += '\n'
        
        return new_line, True
    
    def convert_file(self, input_file: str, output_file: str, dry_run: bool = False) -> dict:
        """Convert G-code file, optionally in dry-run mode."""
        with open(input_file, 'r') as f:
            lines = f.readlines()
        
        output_lines = []
        conversions = []
        
        # Track if the PREVIOUS line was converted from G1 to G0
        was_prev_line_converted = False 
        
        for line_num, line in enumerate(lines, 1):
            stripped_line = line.strip()
            
            # 1. Try to convert BEFORE executing (using the state *before* the move)
            new_line, converted = self.convert_line(line, self.simulator.state)
            line_for_execution = new_line if converted else line
            
            # --- CRITICAL FIX: Explicit G1 Injection for Output and Execution ---
            # If the line was *not* converted:
            if not converted:
                parsed = self.simulator.parse_line(stripped_line)
                
                # Check for: Modal motion command (has coords)
                is_motion = any(k in parsed for k in ['X', 'Y', 'Z', 'I', 'J', 'K'])
                # Check if it lacks an explicit G command
                has_no_g_code = 'G' not in parsed
                
                # If the previous line was converted (set modal G0) AND this is a modal motion, 
                # we must inject G1 to resume feed rate, both for the output and the simulator.
                if is_motion and has_no_g_code and was_prev_line_converted:
                    
                    # Inject G1 for the output line (new_line)
                    new_line = 'G1 ' + stripped_line
                    if line.endswith('\n'):
                        new_line += '\n'
                        
                    # Also use G1 injected line for simulator execution
                    line_for_execution = new_line
            
            # Append the (potentially G1-injected or G0-converted) line to output
            output_lines.append(new_line)
            
            # 2. Log conversion if it happened (G1 -> G0)
            if converted:
                conversions.append({
                    'line_num': line_num,
                    'original': stripped_line,
                    'converted': new_line.strip(),
                    'z_position': self.simulator.state.z
                })
            
            # 3. Execute in simulator to track state for next line
            self.simulator.execute_line(line_for_execution)
            
            # 4. Update state tracker for next loop iteration
            was_prev_line_converted = converted
            
        # Write output if not dry run
        if not dry_run:
            with open(output_file, 'w') as f:
                f.writelines(output_lines)
        
        return {
            'total_lines': len(lines),
            'conversions': conversions,
            'move_history': self.simulator.move_history
        }

def main():
    if len(sys.argv) < 2:
        print("G-code Rapid Move Converter with Simulator and Time Estimator")
        print("=" * 60)
        print("\nUsage: python script.py <input_file> [output_file] [options]")
        print("\nOptions:")
        print("  --z-safe=<height>    Z height for safe rapid moves (default: 17.0)")
        print("  --aggressive         Convert all moves at safe height")
        print("  --rapid-rate=<rate>  Rapid speed for G0 time estimate (default: 5000.0 mm/min)")
        print("  --dry-run            Preview changes without modifying file")
        print("\nExamples:")
        print("  python script.py input.nc --dry-run")
        print("  python script.py input.nc output.nc --z-safe=16.5 --rapid-rate=8000")
        sys.exit(1)
    
    # Parse arguments
    input_file = sys.argv[1]
    output_file = None
    z_safe = 17.0
    conservative = True
    rapid_rate = 5000.0 # Default set to 5000 mm/min
    dry_run = False
    
    for arg in sys.argv[2:]:
        if arg.startswith('--z-safe='):
            z_safe = float(arg.split('=')[1])
        elif arg == '--aggressive':
            conservative = False
        elif arg.startswith('--rapid-rate='):
            rapid_rate = float(arg.split('=')[1])
        elif arg == '--dry-run':
            dry_run = True
        elif not arg.startswith('--'):
            output_file = arg
    
    # Generate output filename if not provided
    if output_file is None and not dry_run:
        input_path = Path(input_file)
        output_file = str(input_path.parent / (input_path.stem + '_rapid' + input_path.suffix))
    
    # Run conversion
    print(f"\n{'DRY RUN - ' if dry_run else ''}Converting G-code")
    print("=" * 60)
    print(f"Input:  {input_file}")
    if not dry_run:
        print(f"Output: {output_file}")
    print(f"Safe Z: {z_safe} mm")
    print(f"Mode:   {'Aggressive' if not conservative else 'Conservative'}")
    print(f"Rapid Rate: {rapid_rate} mm/min (for time estimate)")
    print()
    
    converter = GCodeConverter(z_safe=z_safe, conservative=conservative, rapid_rate=rapid_rate)
    result = converter.convert_file(input_file, output_file or 'dry_run.nc', dry_run=dry_run)
    
    # Display results
    print(f"Analysis Complete!")
    print(f"Total lines: {result['total_lines']}")
    print(f"Conversions: {len(result['conversions'])}")
    
    # Display total time
    total_time_s = converter.simulator.state.total_time_seconds
    hours = int(total_time_s // 3600)
    minutes = int((total_time_s % 3600) // 60)
    seconds = int(total_time_s % 60)
    
    print("-" * 60)
    print(f"Estimated Run Time: {hours:02d}h {minutes:02d}m {seconds:02d}s ⏱️")
    print("-" * 60)
    
    if result['conversions']:
        print("\nConversions made (G1 -> G0):")
        print("-" * 60)
        for conv in result['conversions'][:10]:  # Show first 10
            print(f"Line {conv['line_num']} (Z={conv['z_position']:.2f}):")
            print(f"  Before: {conv['original']}")
            print(f"  After:  {conv['converted']}")
            print()
        
        if len(result['conversions']) > 10:
            print(f"... and {len(result['conversions']) - 10} more conversions")
    
    if dry_run:
        print("\n*** DRY RUN MODE - No files were modified ***")
        print("Review the conversions above, then run without --dry-run to apply changes")
    else:
        print(f"\n✓ Output saved to: {output_file}")
        print("\nIMPORTANT: Simulate this G-code before running on your machine!")

if __name__ == '__main__':
    main()