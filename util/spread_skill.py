import argparse
import yaml
import os
import logging

def parse_arguments():
    parser = argparse.ArgumentParser(description='Process some folders based on dates.')
    parser.add_argument('config_path', type=str, help='Path to the YAML configuration file')
    return parser.parse_args()

def read_yaml_config(config_path):
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)

def reformat(dates, prefix, suffix, script_folder):
    output_files = []
    for date in dates:
        folder_path = f"{prefix}{date}{suffix}"
        
        print(f"Processing folder: {folder_path}")
        input_folder = os.getenv('REFORMAT_INPUT_BASE')
        os.system(f"rm -rf {input_folder}")
        os.system(f"mkdir -p {input_folder}")
        os.system(f"ln -fs {folder_path}/*ADPSFC*.stat ./INPUT/. ")

        # Add your folder processing logic here
        # For example, check if the folder exists:
        if os.path.exists(folder_path):
            os.system(f"python {script_folder}/reformat_ecnt_linetype.py")
            output_ecnt_filename = str(os.getenv('REFORMAT_OUTPUT_BASE')) + "/" + str(os.getenv('OUTPUT_ECNT_FILENAME'))
            os.system(f"mv {output_ecnt_filename} {output_ecnt_filename}.{date}")
            output_files.append(f"{output_ecnt_filename}.{date}")
        else:
            print(f"Does not exist: {folder_path}")

    output_files = " ".join(output_files)
    os.system(f"cat {output_files} > {output_ecnt_filename}")
    print(f'cat {output_files} > {output_ecnt_filename}')
    
def aggregate():

    os.system("python aggregate_ecnt.py")

def plot():

    os.system("python plot_spread_skill.py")

def main():
    args = parse_arguments()
    config = read_yaml_config(args.config_path)

    fcst_dir = os.getenv('REFORMAT_INPUT_BASE')

    raise Exception(f"{fcst_dir}")
    return


    dates = config['dates']
    prefix = config['prefix']
    suffix = config['suffix']
    scripts_folder = config['scripts_folder']

    os.environ['REFORMAT_YAML_CONFIG_NAME'] = config['config_folder'] + "/reformat_ecnt.yaml"
    os.environ['AGGREGATE_YAML_CONFIG_NAME'] = config['config_folder'] + "/aggregate_ecnt.yaml"
    os.environ["PLOTTING_YAML_CONFIG_NAME"] = config['config_folder'] + "/plot_spread_skill.yaml"


    reformat(dates, prefix, suffix, scripts_folder)
    aggregate()
    plot()

if __name__ == "__main__":
    main()

