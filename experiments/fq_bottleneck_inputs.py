"""Fair reference and exact diversity for the five current full-packing bottlenecks."""
import fq_focus_inputs as inputs

inputs.FAMILIES = {(7, 21, 15), (8, 20, 12), (6, 22, 16),
                   (10, 23, 14), (9, 22, 16)}

if __name__ == '__main__':
    inputs.main()
