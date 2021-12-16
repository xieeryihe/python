import sys
import getopt
import time
import Checksum
import BasicSender

max_message_len = 1472

"""
实现原理是：每接收一个包，就标记为已收到，然后从头查看窗口，将从开始能pop的全pop掉
比如发了1，2，3，4，收到了1，3，那么收到1消息时，就检查，发现1前面没有了，就pop一次，
等价于从开始检查，发现1收到了，pop掉一个。
如果发了1,2,3,4，收到了3，那么收到3消息时，就检查，发现1，2都没收到，那就不pop，
从收到的3开始检查，往前走发现有没收到的，什么都不做。


稍微需要注意的是超时处理，因为超时后要把所有的包都发一遍，不能在一次循环里同时pop，
采用上述逻辑，只需要循环send，receive（标记逻辑写在receive里），最后不用handle_response，只需要pop_all即可。
或者：handle_response逻辑只写标记的逻辑，pop_all另外调用。建议后者。

注意：pop_all和handle_response分开写的主要目的是处理超时。因为超时要发送所有的包。
"""


class MyPacket:
    def __init__(self, seqno=-1, packet_string=""):
        self.seqno = seqno
        self.packet_string = packet_string
        self.last_time = time.time()
        self.timeout = 0.5
        self.received = False

    def packet_timeout(self):
        """返回是否超时，"""
        this_time = time.time()
        if this_time - self.last_time > self.timeout:
            self.last_time = this_time
            return True
        else:
            self.last_time = this_time
            return False


class Sender(BasicSender.BasicSender):

    def __init__(self, dest, port, filename, debug=False, sack_mode=False):
        super(Sender, self).__init__(dest, port, filename, debug)
        self.packet_list = []
        self.max_len = 5
        self.send_base = 0
        self.next_seq = 0
        self.sack_mode = sack_mode

    def if_timeout(self):
        """等待包的列表中是否有超时的包"""
        list_len = len(self.packet_list)
        if list_len > 0:
            for i in range(0, list_len):
                if self.packet_list[i].packet_timeout():
                    return True
        return False

    def add_packet(self, packet):
        """添加窗口中等待确认"""
        if self.next_seq - self.send_base < self.max_len:
            self.packet_list.append(packet)
            # print("add seqno: %d" % packet.seqno)
            self.next_seq += 1

    def pop_packet(self, index=0):
        """pop掉列表的指定索引元素"""
        # print("list length:" + str(len(self.packet_list)))
        if index < len(self.packet_list):
            # print("pop seqno: %d" % self.packet_list[0].seqno)
            self.packet_list.pop(index)
            self.send_base += 1

    def pop_all(self):
        """pop掉列表中所有能pop的"""
        while self.packet_list:
            if self.packet_list[0].received:
                self.pop_packet()
            else:
                # print("packet %d doesn't received" % self.packet_list[0].seqno)
                break

    def print_list(self):
        for i in range(0, len(self.packet_list)):
            print("seqno : %d" % self.packet_list[i].seqno)

    def send(self, packet, address=None):
        super(Sender, self).send(packet.packet_string)
        # print("send:" + packet.packet_string[0:15])

    def receive(self, timeout=None):
        """注意：timeout是浮点数，单位为秒"""
        response = super(Sender, self).receive(0.01)  # 接收包的超时设为0.01s
        if response:
            response = response.decode()
            # print("response: " + response)
        return response

    def handle_timeout(self):
        # print("handle timeout")
        list_len = len(self.packet_list)
        response = None
        if self.sack_mode:
            for i in range(0, list_len):
                self.send(self.packet_list[i])
                response = self.receive()
                self.handle_response(response)
            self.pop_all()
        else:
            for i in range(0, list_len):
                self.send(self.packet_list[i])
                response = self.receive()
            self.handle_response(response)

    def handle_response(self, response):
        """
        处理response，只进行标记操作
        一个一般的非选择重传的response格式：ack|5|3870715478
        选择重传格式：sack|1;3,4|<checksum>
        """
        if not response:
            return False
        if Checksum.validate_checksum(response):
            # print("recv: %s" % response)
            # self.print_list()
            if self.sack_mode:
                msg, ack_string, reported_checksum = response.rsplit('|', 2)
                ack, sack_string = ack_string.rsplit(';',1)

                if sack_string:
                    sack_list = sack_string.split(',')
                else:
                    sack_list = []
                for packet in self.packet_list:
                    if packet.seqno < int(ack):
                        packet.received = True
                    if sack_list:
                        for sack in sack_list:
                            if packet.seqno == int(sack):
                                packet.received = True
            else:
                # print("recv: %s" % response)
                msg, ack, reported_checksum = response.rsplit('|', 2)
                # print("ack: " + ack)
                ack = int(ack)
                while self.packet_list: # 正常情况下，只用pop一次就行了，但是为了方便timeout处理，就写成了while的逻辑，且pop的条件是<而不是==
                    # self.print_list()
                    if self.packet_list[0].seqno < ack:  # 一定是按seqno从小到大发包的
                        # print("pop seqno %d" % self.packet_list[0].seqno)
                        self.pop_packet()
                    else:  # 如果最小的seq >= ack，说明该ack之前的包都已经确认过了，简单丢弃
                        break

        else:
            print("recv: %s <--- CHECKSUM FAILED" % response)

    # Main sending loop.
    def start(self):
        msg = self.infile.read(max_message_len)
        msg_type = None
        while not msg_type == 'end':
            if self.if_timeout():
                self.handle_timeout()
                continue

            next_msg = self.infile.read(max_message_len)
            msg_type = 'data'
            if self.next_seq == 0:
                msg_type = 'start'
            elif next_msg == "":
                msg_type = 'end'

            packet_string = self.make_packet(msg_type, self.next_seq, msg)
            packet = MyPacket(seqno=self.next_seq, packet_string=packet_string)
            while True:
                if self.next_seq - self.send_base < self.max_len:
                    self.send(packet)
                    self.add_packet(packet)  # 只有新发送包成功的时候才需要add
                    response = self.receive()
                    self.handle_response(response)
                    self.pop_all()  # 在主程序循环中，每次接收到response都要pop_all，非sack_mode全是false，不用管
                    break  # 只有发包成功才能停止循环，
                else:
                    self.handle_timeout()  # 否则就当超时处理
            msg = next_msg

        # 如果一个文件的包都发完了，最后packet_list还有元素的话，那就说明剩下的全是超时没发完的，直接用超时处理程序即可
        while self.packet_list:
            # print("in last session")
            self.handle_timeout()
        self.infile.close()
        self.sock.close()

    def test(self):
        msg1 = self.infile.read(max_message_len)
        msg2 = self.infile.read(max_message_len)
        msg3 = self.infile.read(max_message_len)
        msg4 = self.infile.read(max_message_len)
        packet_string1 = self.make_packet("start", 0, msg1)
        packet_string2 = self.make_packet("data", 1, msg2)
        packet_string3 = self.make_packet("data", 2, msg3)
        packet_string4 = self.make_packet("end", 3, msg4)

        packet1 = MyPacket(seqno=0, packet_string=packet_string1)
        response = self.receive()
        self.handle_response(response)
        print("handle out")
        time.sleep(1)
        if self.if_timeout():
            print("time out,send all packet again")
            self.handle_timeout()

        packet2 = MyPacket(seqno=1, packet_string=packet_string2)
        packet3 = MyPacket(seqno=2, packet_string=packet_string3)
        packet4 = MyPacket(seqno=3, packet_string=packet_string4)

    def log(self, msg):
        if self.debug:
            print(msg)


'''
This will be run if you run this script from the command line. You should not
change any of this; the grader may rely on the behavior here to test your
submission.
'''
if __name__ == "__main__":
    def usage():
        print("RUDP Sender")
        print("-f FILE | --file=FILE The file to transfer; if empty reads from STDIN")
        print("-p PORT | --port=PORT The destination port, defaults to 33122")
        print("-a ADDRESS | --address=ADDRESS The receiver address or hostname, defaults to localhost")
        print("-d | --debug Print debug messages")
        print("-h | --help Print this usage message")
        print("-k | --sack Enable selective acknowledgement mode")


    opts = ""
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "f:p:a:dk", ["file=", "port=", "address=", "debug=", "sack="])
    except Exception:
        usage()
        exit()

    Port = 33122
    Dest = "localhost"
    Filename = None
    Debug = False
    SackMode = False

    for o, a in opts:
        if o in ("-f", "--file="):
            Filename = a
        elif o in ("-p", "--port="):
            Port = int(a)
        elif o in ("-a", "--address="):
            Dest = a
        elif o in ("-d", "--debug="):
            Debug = True
        elif o in ("-k", "--sack="):
            SackMode = True

    s = Sender(Dest, Port, Filename, Debug, SackMode)
    try:
        s.start()
        # s.test()
    except (KeyboardInterrupt, SystemExit):
        exit()
