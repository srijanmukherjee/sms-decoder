"""
Filter out all non-tnx related sms from the csv file
"""

import json
from typing import Callable, List
import pandas
import fire


def extract_bank_entities(json_sms_entities_file) -> List[str]:
    df = pandas.read_json(json_sms_entities_file, orient="table")
    values = df.values
    bank_entites = set()
    for value in values:
        if "bank" in value[1].lower():
            bank_entites.add(str(value[0]))
    return list(bank_entites)


def address_in_bank_entities(address, bank_entities):
    address = address.lower()
    for entity in bank_entities:
        entity = entity.lower()
        if entity in address:
            return True
    return False


def create_filter_by_bank_entities(bank_entities: List[str]) -> Callable:
    def filter(row):
        return address_in_bank_entities(str(row["address"]), bank_entities)

    return filter


def main(csv_filepath: str, json_sms_entities_file: str, output_filepath: str):
    df = pandas.read_csv(csv_filepath)
    initial_len = len(df)
    df = df[["address", "updateAt", "text", "entity"]]
    # print(df.iloc[0])
    bank_entities = extract_bank_entities(json_sms_entities_file)

    bank_mask = df.apply(create_filter_by_bank_entities(bank_entities), 1)
    df = df[bank_mask]

    print(f"filtered out {initial_len - len(df)} sms")

    output_json = []

    for row in df.values:
        output_json.append({"address": row[0], "body": row[2]})

    with open(output_filepath, "w") as fp:
        json.dump(output_json, fp, indent=4)


if __name__ == "__main__":
    fire.Fire(main, name="filter bank sms")
