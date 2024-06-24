"""Main module for the load-tester"""

import cProfile
import pstats
from logging import Logger
from multiprocessing import Process, current_process
from time import time

import numpy as np

from logprep.generator.kafka.configuration import Configuration
from logprep.generator.kafka.document_loader import DocumentLoader
from logprep.generator.kafka.document_sender import DocumentSender


def get_record_cnt_for_process(config: Configuration, idx: int) -> int:
    """Get count for documents to send for process determined by index"""
    if idx >= config.count:
        return 0

    cnt_per_process = max(config.count // config.process_count, 1)
    if idx < config.process_count - 1:
        return cnt_per_process
    if cnt_per_process * idx <= config.count:
        return config.count - cnt_per_process * idx
    return 0


def run(config: Configuration, shared_dict: dict, count: int, document_chunk: list, logger: Logger):
    """Sends documents to Kafka until desired count has been reached"""
    if config.profile:
        cprofile = cProfile.Profile()
        cprofile.enable()

    proc_name = current_process().name
    logger.info(f"{proc_name} started with {len(document_chunk)} source documents")
    shared_dict[f"{proc_name}_sent"] = 0

    document_sender = DocumentSender(config, logger)

    start = time()
    sent_cnt = document_sender.send(count, document_chunk)

    elapsed_time = time() - start

    shared_dict[f"{proc_name}_time"] = elapsed_time
    shared_dict[f"{proc_name}_sent"] = sent_cnt
    document_sender.shut_down()
    logger.info(f"{proc_name} did send {sent_cnt} documents")

    if config.profile:
        print(f'Profiling for Process with name "{proc_name}":\n')
        cprofile.disable()
        pstats.Stats(cprofile).strip_dirs().sort_stats("cumtime").print_stats()


def run_processes(config: Configuration, shared_dict: dict, logger: Logger):
    """Split data for each process and run processes to send data to Kafka"""
    document_loader = DocumentLoader(config, logger)
    documents = document_loader.get_documents()
    document_loader.shut_down()
    document_chunks = np.array_split(documents, config.process_count)
    processes = []
    for idx in range(config.process_count):
        insert_count = get_record_cnt_for_process(config, idx)
        document_chunks[idx] = (
            document_chunks[idx]
            if insert_count >= len(document_chunks[idx])
            else document_chunks[idx][:insert_count]
        )
        processes.append(
            Process(
                target=run,
                args=(config, shared_dict, insert_count, document_chunks[idx], logger),
            )
        )
    for process in processes:
        process.start()
    for process in processes:
        process.join()
