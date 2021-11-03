import copy
import json
import logging
import sys
from datetime import datetime
from os import mkdir


from stonesoup.serialise import YAML

from inputmanager import InputManager
from runmanagermetrics import RunmanagerMetrics


def read_json(json_input):
    """ Reads JSON Files and stores in dictionary

    Args:
        json_input : json file filled with parameters
    """
    with open(json_input) as json_file:
        json_data = json.load(json_file)
        return json_data


def run(config_path, parameters_path, groundtruth_setting, output_path=None):
    """Run the run manager

    Args:
        config_path : Path of the config file
        parameters_path : Path of the parameters file
        groundtruth_setting : Checks if there is a ground truth available in the config file
    """
    logging.basicConfig(filename='simulation.log', encoding='utf-8', level=logging.INFO)
    input_manager = InputManager()
    json_data = read_json(parameters_path)
    trackers_combination_dict = input_manager.generate_parameters_combinations(
        json_data["parameters"])
    combo_dict = input_manager.generate_all_combos(trackers_combination_dict)

    try:
        with open(config_path, 'r') as file:
            tracker, ground_truth, metric_manager = read_config_file(file)
    except Exception as e:
        print(e)
        logging.error(f'{datetime.now()} : {e}')

    if ground_truth is None:
        try:
            ground_truth = tracker.detector.groundtruth
        except Exception as e:
            logging.error(f'{datetime.now()} : {e}')
            print(f'No groundtruth in tracker detector {e}', flush=True)

    trackers = []
    ground_truths = []
    metric_managers = []

    trackers, ground_truths, metric_managers = set_trackers(
        combo_dict, tracker, ground_truth, metric_manager)
    now = datetime.now()
    dt_string = now.strftime("%d_%m_%Y_%H_%M_%S")
    for idx in range(0, len(trackers)):
        for runs_num in range(0, json_data["configuration"]["runs_num"]):
            dir_name = f"metrics_{dt_string}/simulation_{idx}/run_{runs_num}"
            RunmanagerMetrics.parameters_to_csv(dir_name, combo_dict[idx])
            RunmanagerMetrics.generate_config(
                dir_name, trackers[idx], ground_truths[idx], metric_managers[idx])
            if groundtruth_setting == 0:
                groundtruth = trackers[idx].detector.groundtruth
            else:
                groundtruth = ground_truths[idx]
            print("RUN")
            run_simulation(trackers[idx], groundtruth, metric_managers[idx],
                           dir_name, groundtruth_setting, idx, combo_dict)
    
    # Final line of the log show total time taken to run.
    logging.info(f'All simulations completed. Time taken to run: {datetime.now() - now}')



def run_simulation(tracker, ground_truth, metric_manager, dir_name, groundtruth_setting, index, combos):
    """Start the simulation

    Args:
        tracker: Tracker
        groundtruth: GroundTruth
        metric_manager: Metric Manager
        dir_name: Directory name for saving the simulations
        groundtruth_setting: unsued
        index: Keeps a track of which simulation is being ran
        combos: List of combinations for logging the parameters for each simulation.
    """

    detector = tracker.detector
    log_time = datetime.now()
    try:
        groundtruth = set()
        detections = set()
        tracks = set()
        timeFirst = datetime.now()
        for time, ctracks in tracker:
            # Update groundtruth, tracks and detections
            #groundtruth.update(tracker.detector.groundtruth.groundtruth_paths)

            try:
                RunmanagerMetrics.groundtruth_to_csv(dir_name, ground_truth.groundtruth_paths)
            except:
                try:
                    RunmanagerMetrics.groundtruth_to_csv(dir_name, ground_truth)
                except:
                    pass
            # tracks.update(ctracks)
            # detections.update(tracker.detector.detections)

            RunmanagerMetrics.tracks_to_csv(dir_name, ctracks)
            RunmanagerMetrics.detection_to_csv(dir_name, tracker.detector.detections)


            try:
                if metric_manager is not None:
                    # Generate the metrics
                    try:
                        metric_manager.add_data(ground_truth.groundtruth_paths, ctracks, tracker.detector.detections, overwrite=False)
                    except:
                        metric_manager.add_data(ground_truth, ctracks, tracker.detector.detections, overwrite=False)
            except Exception as e:
                print(f"Error with metric manager.")
                logging.error(f"{datetime.now()}, Error: {e}")
            # print(tracker.initiator.number_particles)
        
        try:
            metrics = metric_manager.generate_metrics()
            RunmanagerMetrics.metrics_to_csv(dir_name, metrics)
        except Exception as e:
            print("Metric manager: {}".format(e))          
        timeAfter = datetime.now()

        timeTotal = timeAfter-timeFirst
        print(timeTotal)
        

    except Exception as e:
        logging.error(f'{log_time}: Simulation {index} failed in {datetime.now() - log_time}. error: {e}  . Parameters: {combos[index]}')
        print(f'Failed to run Simulation: {e}', flush=True)

    else:
        logging.info(f'{log_time}: Simulation {index} / {len(combos)-1} ran successfully in {datetime.now() - log_time}. With Parameters: {combos[index]}')
        print('Success!', flush=True)


def set_trackers(combo_dict, tracker, ground_truth, metric_manager):
    """Set the trackers, groundtruths and metricmanagers list (stonesoup objects)

    Args:
        combo_dict (dict): dictionary of all the possible combinations of values

        tracker (tracker): stonesoup tracker

        groundtruth (groundtruth): stonesoup groundtruth

        metric_manager (metricmanager): stonesoup metric_manager

    Returns:
        list: list of trackers
        list: list of groundtruths
        list: list of metric managers
    """
    trackers = []
    ground_truths = []
    metric_managers = []

    for parameter in combo_dict:
        tracker_copy, ground_truth_copy, metric_manager_copy = copy.deepcopy(
            (tracker, ground_truth, metric_manager))
        for k, v in parameter.items():
            split_path = k.split('.')
            path_param = '.'.join(split_path[1::])
            split_path = split_path[1::]

            # setattr(tracker_copy.initiator, split_path[-1], v)
            set_param(split_path, tracker_copy, v)
        trackers.append(tracker_copy)
        ground_truths.append(ground_truth_copy)
        metric_managers.append(metric_manager_copy)

    return trackers, ground_truths, metric_managers


def set_param(split_path, el, value):
    """[summary]

    Args:
        split_path ([type]): [description]
        el ([type]): [description]
        value ([type]): [description]
    """
    if len(split_path) > 1:
       # print(split_path[0])
        newEl = getattr(el, split_path[0])
        set_param(split_path[1::], newEl, value)
    else:
        # print(value)
        # print(getattr(el,split_path[0]))

        setattr(el, split_path[0], value)
        # print(el)


def read_config_file(config_file):
    """Read the configuration file

    Args:
        config_file (file path): file path of the configuration file

    Returns:
        trackers,ground_truth,metric_manager: trackers, ground_truth and metric manager stonesoup structure
    """
    config_string = config_file.read()
    # Configs with Tracker + GroundTruth + Metric Manager
    # Finds the right data from configs (might need changing)
    try:
        tracker, ground_truth, metric_manager = YAML('safe').load(config_string)
        print("Tracker, groundtruth and metric manager found.")
    except:
        try:
            tracker, gt_mm = YAML('safe').load(config_string)
            if gt_mm == tracker.detector.groundtruth:
                print("Tracker and groundtruth found.")
                metric_manager = None
            else:
                print("Tracker and metric manager found.")
                gt_mm = None
        except:
            try:
                tracker = YAML('safe').load(config_string)[0]  # Returns list containing tracker only
                print("Tracker found.")
                gt_mm = None
                metric_manager = None
            except Exception as e:
                tracker = None
                print(f'Could not find tracker: {e}', flush=True)

    return tracker, ground_truth, metric_manager


if __name__ == "__main__":
    args = sys.argv[1:]

    try:
        configInput = args[0]
    except:
        configInput = "C:\\Users\\Davidb1\\Documents\\Python\\data\\testConfigs\\testConfigs\\metrics_config_v5.yaml"
        # configInput= "C:\\Users\\Davidb1\\Documents\\Python\\data\\config.yaml"

    try:
        parametersInput = args[1]
    except:
        parametersInput = "C:\\Users\\Davidb1\\Documents\\Python\\data\\parameters.json"
        #parametersInput= "C:\\Users\\gbellant\\Documents\\Projects\\Serapis\\dummy3.json"

    try:
        groundtruthSettings = args[2]
    except:
        groundtruthSettings = 1

    run(configInput, parametersInput, groundtruthSettings)
