from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from collections import deque
import xml.etree.ElementTree as et
import json
import sys

messagesDeque = deque()
filters = {
    "from": None,
    "to": None,
    "date": None,
    "title": None
}


class QueueHandler(BaseHTTPRequestHandler):
    def do_sendMessage(self):
        bin_message = self.rfile.read(int(self.headers["Content-Length"]))
        xml_message = et.fromstringlist(bin_message.decode("UTF-8"))
        messagesDeque.append(xml_message)
        self.set_response()

    def do_getMessage(self):
        try:
            message = messagesDeque.popleft()
        except IndexError:
            message = et.Element("Error")
            message.text = "Message queue is empty"

        message = et.tostring(message, encoding="utf-8", method="xml")
        self.set_response(content_type="text/xml", data_to_send=message)

    def do_findMessages(self):
        # Fills filter dict from json file received with find request
        bin_filter = self.rfile.read(int(self.headers["Content-Length"]))
        json_filter = json.loads(bin_filter)["filter"]
        for key in json_filter.keys():
            filters[key] = json_filter[key]

        reversed_date = self.reverse_date()
        filters["date"] = reversed_date

        messages_indexes = self.filter_queue()

        found_messages = self.construct_response(messages_indexes)

        found_messages = et.tostring(found_messages, encoding="utf-8", method="xml")
        self.set_response(content_type="text/xml", data_to_send=found_messages)

    def do_POST(self):

        if self.path == "/sendMessage":
            self.do_sendMessage()
        elif self.path == "/findMessages":
            self.do_findMessages()

    def do_GET(self):

        if self.path == "/getMessage":
            self.do_getMessage()

    def set_response(self, content_type="text/plain", data_to_send=b""):

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(data_to_send)

    def reverse_date(self):
        reversed_date = ""
        if filters["date"] is not None:
            reversed_date += filters["date"][6:10]
            reversed_date += "-"
            reversed_date += filters["date"][3:5]
            reversed_date += "-"
            reversed_date += filters["date"][0:2]
            filters["date"] = reversed_date
        return reversed_date

    def filter_queue(self):
        messages_indexes = list()
        for i in range(len(messagesDeque)):
            message: et.Element = messagesDeque[i]
            matched = False
            for child in message.iter():
                try:
                    filter_tag = child.tag.lower() if child.tag.lower() != "timestamp" else "date"
                    if filters[filter_tag] is None:
                        continue
                    if filters[filter_tag] in child.text:
                        matched = True
                        break
                except KeyError:
                    continue
            if matched:
                messages_indexes.append(i)
        return messages_indexes

    def construct_response(self, messages_indexes):
        found_messages = et.Element("Messages")
        if len(messages_indexes) == 0:
            error = et.Element("Error")
            error.text = "No messages was found matching this filter"
            found_messages.append(error)
        else:
            for i in messages_indexes:
                found_messages.append(messagesDeque[i])
        return found_messages


if __name__ == "__main__":
    port = int(sys.argv[2])
    with HTTPServer(("127.0.0.1", port), QueueHandler) as httpServer:
        try:
            print("Listening to port " + str(port))
            httpServer.serve_forever()
        except KeyboardInterrupt:
            httpServer.server_close()
            print("Server stopped")
