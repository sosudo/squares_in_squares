"""Freeze current orientation-fair minima and diversity for two productive families."""
import fq_focus_inputs as inputs

inputs.FAMILIES = {(7, 21, 15), (9, 22, 16)}

if __name__ == '__main__':
    inputs.main()
