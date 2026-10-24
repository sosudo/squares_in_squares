"""Freeze the two orientations of the current 7x21+15 minimum and diversity."""
import fq_focus_inputs as inputs

inputs.FAMILIES = {(7, 21, 15)}

if __name__ == '__main__':
    inputs.main()
