# Copyright (c) 2021 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import unittest

import paddle

paddle.enable_static()


class TestFleetMetaOptimizer(unittest.TestCase):
    def setUp(self):
        os.environ["PADDLE_TRAINER_ID"] = "1"
        os.environ["PADDLE_TRAINER_ENDPOINTS"] = (
            "127.0.0.1:36001,127.0.0.1:36002"
        )

    def test_pipeline_optimizer(self):
        from paddle.distributed import fleet
        from paddle.distributed.fleet.base import role_maker

        role = role_maker.PaddleCloudRoleMaker(is_collective=True)
        fleet.init(role)
        with paddle.base.device_guard("gpu:0"):
            input_x = paddle.static.data(
                name="x", shape=[-1, 32], dtype='float32'
            )
            input_y = paddle.static.data(name="y", shape=[-1, 1], dtype='int64')
            fc_1 = paddle.static.nn.fc(x=input_x, size=64, activation='tanh')
            fc_2 = paddle.static.nn.fc(x=fc_1, size=64, activation='tanh')
            fc_3 = paddle.static.nn.fc(x=fc_2, size=64, activation='tanh')
            fc_4 = paddle.static.nn.fc(x=fc_3, size=64, activation='tanh')
            fc_5 = paddle.static.nn.fc(x=fc_4, size=64, activation='tanh')
            fc_6 = paddle.static.nn.fc(x=fc_5, size=64, activation='tanh')

        with paddle.base.device_guard("gpu:1"):
            fc_7 = paddle.static.nn.fc(x=fc_6, size=64, activation='tanh')
            prediction = paddle.static.nn.fc(
                x=[fc_7], size=2, activation='softmax'
            )
            cost = paddle.nn.functional.cross_entropy(
                input=prediction,
                label=input_y,
                reduction='none',
                use_softmax=False,
            )
            avg_cost = paddle.mean(x=cost)

        strategy = paddle.distributed.fleet.DistributedStrategy()
        strategy.pipeline = True
        strategy.pipeline_configs = {
            'micro_batch_size': 1,
            'accumulate_steps': 2,
            'schedule_mode': '1F1B',
        }

        checkpoints = ['fc_5.tmp_0', 'fc_7.tmp_0']
        strategy.recompute = True
        strategy.recompute_configs = {
            "checkpoints": checkpoints,
            "enable_offload": False,
            "checkpoint_shape": [],
        }

        optimizer = paddle.optimizer.Adam(0.01)
        optimizer = fleet.distributed_optimizer(optimizer, strategy=strategy)
        optimizer.minimize(avg_cost)


if __name__ == "__main__":
    unittest.main()
