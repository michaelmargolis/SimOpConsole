using System;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

class HeartbeatServer
{
    const int HEARTBEAT_PORT = 10030;
    const int CHECK_INTERVAL = 5000; // milliseconds to recheck process list

    static bool IsProgramRunning(string programName)
    {
        try
        {
            // Run the tasklist command to get the list of running processes
            Process process = new Process();
            process.StartInfo.FileName = "tasklist";
            process.StartInfo.RedirectStandardOutput = true;
            process.StartInfo.UseShellExecute = false;
            process.StartInfo.CreateNoWindow = true;
            process.Start();

            string output = process.StandardOutput.ReadToEnd();
            process.WaitForExit();

            // Check if the program name is in the output
            return output.IndexOf(programName, StringComparison.OrdinalIgnoreCase) >= 0;
        }
        catch (Exception e)
        {
            Console.WriteLine($"Error checking for program: {e}");
            return false;
        }
    }

    static void Main()
    {
        UdpClient udpClient = new UdpClient(HEARTBEAT_PORT);
        udpClient.Client.ReceiveTimeout = 1000;

        Console.SetWindowSize(80, 8);
        Console.WriteLine($"[Heartbeat Server] Listening on UDP port {HEARTBEAT_PORT}...");

        bool xplaneState = IsProgramRunning("X-Plane");
        DateTime lastCheck = DateTime.Now;

        while (true)
        {
            try
            {
                // Refresh state periodically
                if ((DateTime.Now - lastCheck).TotalMilliseconds > CHECK_INTERVAL)
                {
                    xplaneState = IsProgramRunning("X-Plane");
                    lastCheck = DateTime.Now;
                }

                IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, 0);
                byte[] data = udpClient.Receive(ref remoteEndPoint);

                if (Encoding.ASCII.GetString(data).Trim().ToLower() == "ping")
                {
                    string timestamp = DateTime.Now.ToString("HH:mm:ss");
                    string reply = xplaneState ? $"xplane_running" : $"X-Plane not detected";
                    byte[] replyBytes = Encoding.ASCII.GetBytes(reply);
                    udpClient.Send(replyBytes, replyBytes.Length, remoteEndPoint);
                    Console.SetCursorPosition(0, Console.CursorTop); // Move to the start of the current line
                    Console.Write($"Replying {reply} to {remoteEndPoint} at {timestamp}       "); 
                    // Console.WriteLine($"Replying {reply} to {remoteEndPoint}");
                }
            }
            catch (SocketException)
            {
                continue;
            }
            catch (Exception e)
            {
                Console.WriteLine($"\n[ERROR] {e}");
            }
        }
    }
}
