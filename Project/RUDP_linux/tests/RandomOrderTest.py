import random

from tests.BasicTest import BasicTest

"""
This tests random packet drops. We randomly decide to drop about half of the
packets that go through the forwarder in either direction.

Note that to implement this we just needed to override the handle_packet()
method -- this gives you an example of how to extend the basic test case to
create your own.
"""


class RandomOrderTest(BasicTest):
    def handle_packet(self):
        q = self.forwarder.in_queue
        queue_len = len(q)
        for p in q:
            self.forwarder.out_queue.append(p)  # append all
        for i in range(0, queue_len - 1):
            if random.choice([True, False]):
                temp = q[i]
                q[i] = q[i+1]
                q[i+1] = temp
        # empty out the in_queue
        self.forwarder.in_queue = []
