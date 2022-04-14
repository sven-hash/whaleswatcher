from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl
import smtplib


class Monitor:
    def __init__(self, smtpServer, smtpSender, smtpPassword, smtpReceiver, smtpFrom, smtpPort=465):
        self.server = smtpServer
        self.port = smtpPort
        self.senderEmail = smtpSender
        self.receiverEmail = smtpReceiver
        self.password = smtpPassword
        if smtpFrom is not None:
            self.fromHeader = smtpFrom
        else:
            self.fromHeader = smtpSender

    def sendMessage(self, application, error, origText):
        # Try to log in to server and send email
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.server, self.port, context=context) as server:
                server.login(self.senderEmail, self.password)
                server.ehlo()

                message = MIMEMultipart()
                message.add_header('From', self.fromHeader)
                message.add_header('To', self.receiverEmail)
                message.add_header('Subject', f"Error from {application}")
                message.attach(MIMEText(f"Error message: {error}\nTry to send: {origText}", 'plain'))
                server.sendmail(self.senderEmail, self.receiverEmail, message.as_string())

        except Exception as e:
            print(f"SMTP Error: {e}")
        finally:
            server.connect(self.server, self.port)
            server.quit()