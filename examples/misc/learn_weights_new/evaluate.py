"""
checks all result files an writes the best candidates to evaluate.json
"""
import glob
import json
import operator
import pickle
import collections

import statistics
from itertools import groupby




compare = lambda x, y: collections.Counter(x) == collections.Counter(y)



def weights_to_string(weights):
    scaled_weights_string = [str(x) for x in weights]
    return ''.join(scaled_weights_string)


def stats(numbers):
    return {"mean": statistics.mean(numbers),
            "median": statistics.median(numbers)}


def read_file(path):
    # filename = os.path.basename(file_path)
    score_results = {}
    for file_path in glob.glob(path):
        with open(file_path, 'rb') as ff:
            results = pickle.load(ff)
        for result in results:
            for question in result:
                question_scores = score_results.setdefault(question, {})
                weights = result[question][1]
                weights_fixed =[]
                # fix floating error
                for i in weights:
                    weights_fixed.append(round(i, 1))


                comb = question_scores.setdefault(weights_to_string(weights_fixed), {'weights': weights_fixed, 'scores_doc': []})
                comb['scores_doc'].append(result[question][2])
    return score_results


def remove_errors(list):
    """
    returns a list where all -1 are replace with the biggest value and all oder negative entries are removed at all
    :param list:
    :return:
    """
    # remove no annotation error, by replacing with worst distance
    a_max = max(list)
    tmp = [a_max if v is -1 else v for v in list]

    # remove other errors
    result = [x for x in tmp if x and x >= 0]
    return result

def normalize(list):
    """
    this is assuming that there is a min with 0
    :param list:
    :return:
    """
    # find max
    a_max = max(list)
    # set errors to max
    list_error_free = [x if x >= 0 else a_max for x in list]
    # normalize
    result = []
    for entry in list_error_free:
        result.append(entry/a_max)

    return result


def merge_top(a_list, accessor):
    """
    multiple weights can produce the same top-score, this function merges all top weights.
    :param a_list: 
    :param accessor: 
    :return: 
    """
    result = a_list[0]
    weights = []
    result['weights'] = weights

    for entry in a_list:
        if entry[accessor] == result[accessor]:
            a_weight = entry.get('weight')
            if a_weight:
                weights.append(a_weight)
        else:
            break
    return result


def find_golden_weights(a_list):
    """
    checks for an overlap in 'lowest_error' and 'best_dist'
    copies all overlapping weights to golden_weights
    :param results:
    :return:
    """
    result = []
    for lowest_error in a_list['lowest_error']['weights']:
        for best_dist in a_list['best_dist']['weights']:
            if compare(lowest_error, best_dist):
                result.append(lowest_error)
    a_list['golden_weights'] = result



def to_ranges(iterable):
    iterable = sorted(set(iterable))
    for key, group in groupby(enumerate(iterable),
                                        lambda t: t[1] - t[0]):
        group = list(group)
        yield group[0][1], group[-1][1]

def to_ranges_wrapper(iterable):

    # to int
    for ita, i in enumerate(iterable):
        iterable[ita] = int(iterable[ita] * 10)

    result = list(to_ranges(iterable))

    return result

def golden_weights_to_ranges(a_list):
    """
    converts golden weights to ranges per weight to make importance more visible
    [0.1, 0.1] [0.2, 0.1] [0.3, 0.9]

    this function works only well with 0.1 step weights, result is not  converted back to float
    ---->
    {
        0: [1 - 3]
        1: [1 - 1] [0.9 - 0.9]
    }
    "EXPERIMENTAL - NOT VERY WELL TESTED"

    :param a_list: 
    :return: 
    """
    golden_weights = a_list.get('best_dist')['weights']
    if golden_weights and len(golden_weights) > 0:
        # slots for each weight

        weights =  [[] for _ in range(len(golden_weights[0]))]
        #weights = [[]] *
        for combination in golden_weights:
            for i, weight in enumerate(combination):
                weights[i].append(weight)

        result = []
        for weight in weights:
            uniqu_weights = list(set(weight))
            uniqu_weights.sort()
            result.append(
            to_ranges_wrapper(uniqu_weights))
        a_list['golden_groups'] = result

def index_of_best(list):
    """
    low distance is better
    :param list:
    :return:
    """
    a_list = remove_errors(list)
    return list.index(min(a_list))


if __name__ == '__main__':

    # read all available prickles
    score_results = read_file('queue_caches/*processed.prickle')

    # write raw results
    with open('result/evaluation_full' + '.json', 'w') as data_file:
        data_file.write(json.dumps(score_results, sort_keys=False, indent=4))
        data_file.close()

    #
    # 1. Crit.: has a low dist on average per weight (documents are merged)
    # 3. Crit.: weight with lowest error rate per documents (documents are merged)
    score_per_average = {}
    results_error_rate = {}
    for question in score_results:
        for combination_string in score_results[question]:
            combo = score_results[question][combination_string]

            raw_scores = combo['scores_doc']
            scores_cleaned = remove_errors(raw_scores)
            scores_norm = normalize(raw_scores)
            errors = len(raw_scores) - len(scores_cleaned)
            a_sum = sum(scores_norm)

            combo['norm_avg'] = a_sum / len(scores_norm)
            score_per_average.setdefault(question, {})[combination_string] = {
                'score': a_sum,
                'norm_avg': combo['norm_avg'],
                'weight': combo['weights']
            }

            results_error_rate.setdefault(question,{})[combination_string] = {
                'errors': errors,
                'weight': combo['weights']
            }

            # nice formattet full output, if anyone needs is
    nice_format = {}
    for question in score_results:
        question_scores = nice_format.setdefault(question, [])
        for combination_string in score_results[question]:
            combo = score_results[question][combination_string]
            del combo['scores_doc']
            question_scores.append(combo)

    with open('result/evaluation_only_avg' + '.json', 'w') as data_file:
        data_file.write(json.dumps(nice_format, sort_keys=False, indent=4))
        data_file.close()

    # finally, get the best weighting and save it to a file
    final_result = {}
    for question in results_error_rate:

        results_error_rate_list = list(results_error_rate[question].values())
        score_per_average_list = list(score_per_average[question].values())

        results_error_rate_list.sort(key=lambda x: x['errors'], reverse=False)
        score_per_average_list.sort(key=lambda x: x['norm_avg'], reverse=False)

        final_result[question] = {
        #     'lowest_error': merge_top(results_error_rate_list, 'errors'),
            'best_dist': merge_top(score_per_average_list, 'norm_avg')
        }


        #find_golden_weights(final_result[question])


        golden_weights_to_ranges(final_result[question])

    #print(json.dumps(final_result, sort_keys=False, indent=4))

    for question in final_result:
        with open('result/final_result_' +question+ '.json', 'w') as data_file:
            data_file.write(json.dumps(final_result[question], sort_keys=False, indent=4))
            data_file.close()


