import os
import pickle

import numpy as np
import torch
from tqdm import tqdm

from DataProcessing.find_and_load_patient_files import (
    find_patient_files,
    load_patient_data,
)
from DataProcessing.helper_code import get_num_locations, load_wav_file
from DataProcessing.label_extraction import get_murmur, get_outcome
from HumBugDB.LogMelSpecs.compute_LogMelSpecs import waveform_to_examples


def net_feature_loader(
    recalc_features, train_data_directory, test_data_directory, spectrogram_directory
):

    if not os.path.isdir(spectrogram_directory):#判断是否为路径
        os.makedirs(spectrogram_directory)
    if not recalc_features:#创建data/data/spectrograms/spec_train
        #获取训练集数据特征、标签
        print("ture")
        spectrograms_train, murmurs_train, outcomes_train = calc_patient_features(
            train_data_directory
        )
        repeats = torch.zeros((len(spectrograms_train),))
        #？？？？？？？？？？
        for i in range(len(spectrograms_train)):#第i个患者的第j个Mel特征
            for j in range(len(spectrograms_train[i])):
                repeats[i] += len(spectrograms_train[i][j])
        #按照每个患者的特征长度对murmur、outcomes标签重复
        murmurs_train = torch.repeat_interleave(
            torch.Tensor(np.array(murmurs_train)), repeats.to(torch.int32), dim=0
        )
        outcomes_train = torch.repeat_interleave(
            torch.Tensor(np.array(outcomes_train)), repeats.to(torch.int32), dim=0
        )
        spectrograms_train = torch.cat([x for xs in spectrograms_train for x in xs])#将训练集的所有特征展开为一维？
        torch.save(
            spectrograms_train, os.path.join(spectrogram_directory, "spec_train")
        )
        torch.save(murmurs_train, os.path.join(spectrogram_directory, "murmurs_train"))
        torch.save(
            outcomes_train, os.path.join(spectrogram_directory, "outcomes_train")
        )

        spectrograms_test, murmurs_test, outcomes_test = calc_patient_features(
            test_data_directory
        )
        repeats = torch.zeros((len(spectrograms_test),))
        for i in range(len(spectrograms_test)):
            for j in range(len(spectrograms_test[i])):
                repeats[i] += len(spectrograms_test[i][j])
        murmurs_test = torch.repeat_interleave(
            torch.Tensor(np.array(murmurs_test)), repeats.to(torch.int32), dim=0
        )
        outcomes_test = torch.repeat_interleave(
            torch.Tensor(np.array(outcomes_test)), repeats.to(torch.int32), dim=0
        )
        spectrograms_test = torch.cat([x for xs in spectrograms_test for x in xs])
        murmurs_test = torch.Tensor(np.array(murmurs_test))
        outcomes_test = torch.Tensor(np.array(outcomes_test))
        torch.save(spectrograms_test, os.path.join(spectrogram_directory, "spec_test"))
        torch.save(murmurs_test, os.path.join(spectrogram_directory, "murmurs_test"))
        torch.save(outcomes_test, os.path.join(spectrogram_directory, "outcomes_test"))
    else:
        #如果已经有了特征文件夹，加载特征
        print("flase")
        spectrograms_train = torch.load(
            os.path.join(spectrogram_directory, "spec_train")
        )
        murmurs_train = torch.load(os.path.join(spectrogram_directory, "murmurs_train"))
        outcomes_train = torch.load(
            os.path.join(spectrogram_directory, "outcomes_train")
        )
        spectrograms_test = torch.load(os.path.join(spectrogram_directory, "spec_test"))
        murmurs_test = torch.load(os.path.join(spectrogram_directory, "murmurs_test"))
        outcomes_test = torch.load(os.path.join(spectrogram_directory, "outcomes_test"))

    return (
        spectrograms_train,
        murmurs_train,
        outcomes_train,
        spectrograms_test,
        murmurs_test,
        outcomes_test,
    )


def patient_feature_loader(recalc_features, data_directory, output_directory):
    if recalc_features == "True":
        spectrograms, murmurs, outcomes = calc_patient_features(data_directory)#list
        with open(output_directory + "spectrograms", "wb") as fp:
            pickle.dump(spectrograms, fp)
        with open(output_directory + "murmurs", "wb") as fp:
            pickle.dump(murmurs, fp)
        with open(output_directory + "outcomes", "wb") as fp:
            pickle.dump(outcomes, fp)
    else:
        with open(output_directory + "spectrograms", "rb") as fp:
            spectrograms = pickle.load(fp)
        with open(output_directory + "murmurs", "rb") as fp:
            murmurs = pickle.load(fp)
        with open(output_directory + "outcomes", "rb") as fp:
            outcomes = pickle.load(fp)

    return spectrograms, murmurs, outcomes


# Load recordings.
def load_spectrograms(data_directory, data):
    num_locations = get_num_locations(data) #听诊区数目
    recording_information = data.split("\n")[1 : num_locations + 1] #获取各听诊区文件名

    mel_specs = list()
    for i in range(num_locations):
        entries = recording_information[i].split(" ")
        recording_file = entries[2] #对应听诊区的wav文件
        filename = os.path.join(data_directory, recording_file)
        recording, frequency = load_wav_file(filename)
        recording = recording / 32768
        mel_spec = waveform_to_examples(recording, frequency) #这句有问题 换一种logmel特征提取方式？
        mel_specs.append(mel_spec)
    return mel_specs


def calc_patient_features(data_directory):

    murmur_classes = ["Present", "Unknown", "Absent"]
    num_murmur_classes = len(murmur_classes)
    outcome_classes = ["Abnormal", "Normal"]
    num_outcome_classes = len(outcome_classes)

    # Find the patient data files.
    patient_files = find_patient_files(data_directory)#返回该目录下所有的text文件
    num_patient_files = len(patient_files)
    spectrograms = list()
    murmurs = list()
    outcomes = list()
    for i in tqdm(range(num_patient_files)):

        # Load the current patient data and recordings.
        current_patient_data = load_patient_data(patient_files[i])#当前患者的txt内容
        current_spectrograms = load_spectrograms(data_directory, current_patient_data)#提取当前患者各听诊区的Mel谱 list类型
        spectrograms.append(current_spectrograms)#[[[患者1_AV特征],[患者1_PV特征],..]，[[患者2_AV特征],[患者2_PV特征],...]]
        current_murmur = np.zeros(num_murmur_classes, dtype=int)
        murmur = get_murmur(current_patient_data)
        #独热编码
        if murmur in murmur_classes:
            j = murmur_classes.index(murmur)
            current_murmur[j] = 1
        murmurs.append(current_murmur)
        # Outcome
        current_outcome = np.zeros(num_outcome_classes, dtype=int)
        outcome = get_outcome(current_patient_data)
        if outcome in outcome_classes:
            j = outcome_classes.index(outcome)
            current_outcome[j] = 1
        outcomes.append(current_outcome)
        if murmur in murmur_classes:
            j = murmur_classes.index(murmur)
            current_murmur[j] = 1

    return spectrograms, murmurs, outcomes
