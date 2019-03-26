import json
from typing import TextIO, Union

from .etheno import EthenoPlugin

class JSONRPCExportPlugin(EthenoPlugin):
    def __init__(self, out_stream: Union[str, TextIO]):
        self._was_path = isinstance(out_stream, str)
        if self._was_path:
            self._output = open(out_stream, 'w', encoding='utf8')
        else:
            self._output = out_stream
        self._output.write('[')
        self._count = 0

    def before_post(self, post_data):
        if self._count > 0:
            self._output.write(',')
        self._count += 1
        self._output.write('\n')
        json.dump(post_data, self._output)
        self._output.flush()

    def finalize(self):
        if self._count:
            self._output.write('\n')
        self._output.write(']')
        self._output.flush()
        if self._was_path:
            self._output.close()
        if hasattr(self._output, 'name'):
            self.logger.info(f'Raw JSON RPC messages dumped to {self._output.name}')
