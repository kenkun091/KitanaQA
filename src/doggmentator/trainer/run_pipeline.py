import json
import logging
import os
import sys
import numpy as np
import torch
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from transformers import (
    AlbertConfig,
    AlbertForQuestionAnswering,
    AlbertTokenizer,
    BertConfig,
    BertForQuestionAnswering,
    BertTokenizer,
    HfArgumentParser,
    TrainingArguments,
)

from arguments import ModelArguments
from utils import set_seed, load_and_cache_examples, is_apex_available, post_to_slack, build_flow

logger = logging.getLogger(__name__)

MODEL_CLASSES = {
    "albert": (AlbertConfig, AlbertForQuestionAnswering, AlbertTokenizer),
    "bert": (BertConfig, BertForQuestionAnswering, BertTokenizer),
}


if __name__ == "__main__":

    # Initialize args
    parser = HfArgumentParser(dataclass_types=[ModelArguments, TrainingArguments])
    args_file = "/home/ubuntu/searchable/Doggmentator/src/doggmentator/trainer/args.json"
    model_args, training_args = parser.parse_json_file(args_file)

    if model_args.model_type not in list(MODEL_CLASSES.keys()):
        raise NotImplementedError("Model type should be 'bert', 'albert'")
    if not is_apex_available():
        training_args.fp16 = False

    # Setup the environment
    if (
        os.path.exists(training_args.output_dir)
        and os.listdir(training_args.output_dir)
        and training_args.do_train
        and not training_args.overwrite_output_dir
    ):
        raise ValueError(
            f"Output directory ({training_args.output_dir}) already exists and is not empty. Use --overwrite_output_dir to overcome."
        )
    # TODO: check if tmp dirs exist and mkdirs if necessary

    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO if training_args.local_rank in [-1, 0] else logging.WARN,
    )
    logger.warning(
        "Process rank: %s, device: %s, n_gpu: %s, distributed training: %s, 16-bits training: %s",
        training_args.local_rank,
        training_args.device,
        training_args.n_gpu,
        bool(training_args.local_rank != -1),
        training_args.fp16,
    )
    logger.info("Training/evaluation parameters %s", training_args)

    # Set seed
    set_seed(training_args)

    # Load model and tokenizer
    config, model_cls, tokenizer_cls = MODEL_CLASSES[model_args.model_type]
    tokenizer = tokenizer_cls.from_pretrained(
        model_args.tokenizer_name_or_path if model_args.tokenizer_name_or_path else model_args.model_name_or_path,
        cache_dir=model_args.cache_dir,
    )
    model = model_cls.from_pretrained(
        model_args.model_name_or_path,
        cache_dir=model_args.cache_dir,
    )

    # Load training dataset
    if training_args.do_train:
        train_dataset = load_and_cache_examples(model_args, tokenizer)
    else:
        train_dataset = None

    # Load aug dataset
    if training_args.do_train and model_args.do_aug:
        aug_dataset = load_and_cache_examples(model_args, tokenizer, use_aug_path=True)
        logger.info('Concatenete augmented examples to original examples. Train length = {} - Aug length = {}'.format(len(train_dataset), len(aug_dataset)))
        train_dataset += aug_dataset

    f = build_flow(
            (model_args, training_args),
            model=model,
            tokenizer=tokenizer,
            train_dataset=train_dataset)

    if f:
        f.run()

    # TODO: Log Results

    # TODO: Deploy Model
