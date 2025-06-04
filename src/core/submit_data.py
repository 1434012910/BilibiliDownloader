import os
from typing import Any

from tqdm import tqdm

from src.interfaces.submit import DataSubmit


class SubmitData(DataSubmit):
    def submit(self,data):
        submit_type=data.get("submit_type","")
        response=data.get("response","")
        filepath=data.get("filepath","")
        existing_size=data.get("existing_size",0)
        total_size=data.get("total_size",0)
        bv_id=data.get("bv_id","")
        if total_size == 0:
            total_size = None
        if submit_type=="local":
            return self._submit_local(response=response,save_path=filepath,existing_size=existing_size,total_size=total_size,bv_id=bv_id)

    @staticmethod
    def _submit_local(response, save_path, existing_size, total_size,bv_id):
        with open(save_path, 'ab') as file, tqdm(
                desc=bv_id,
                initial=existing_size,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
                    bar.update(len(chunk))
        return {
            "complete": True
        }