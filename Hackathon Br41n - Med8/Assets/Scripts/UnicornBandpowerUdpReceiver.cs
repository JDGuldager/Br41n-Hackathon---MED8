using System;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

public class UnicornBandpowerUdpReceiver : MonoBehaviour
{
    [Header("UDP Settings")]
    public int port = 12345;

    [Header("Debug")]
    public bool logRawMessages = false;

    [Header("Latest Parsed Values")]
    public string latestRawMessage = "";
    public float alphaAverage = 0f;
    public float betaAverage = 0f;
    public float gammaAverage = 0f;

    private Socket socket;
    private Thread receiveThread;
    private volatile bool isRunning = false;

    private readonly object dataLock = new object();
    private readonly float[] latestValues = new float[70];

    void Start()
    {
        StartReceiver();
    }

    void StartReceiver()
    {
        try
        {
            IPEndPoint endPoint = new IPEndPoint(IPAddress.Any, port);

            socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
            socket.Bind(endPoint);

            isRunning = true;
            receiveThread = new Thread(ReceiveLoop);
            receiveThread.IsBackground = true;
            receiveThread.Start();

            Debug.Log($"Listening for Unicorn Bandpower UDP on port {port}");
        }
        catch (Exception ex)
        {
            Debug.LogError("UDP start error: " + ex.Message);
        }
    }

    void ReceiveLoop()
    {
        byte[] receiveBuffer = new byte[4096];

        while (isRunning)
        {
            try
            {
                int numberOfBytesReceived = socket.Receive(receiveBuffer);

                if (numberOfBytesReceived > 0)
                {
                    byte[] messageBytes = new byte[numberOfBytesReceived];
                    Array.Copy(receiveBuffer, messageBytes, numberOfBytesReceived);

                    string message = Encoding.ASCII.GetString(messageBytes).Trim();

                    lock (dataLock)
                    {
                        latestRawMessage = message;
                        ParsePacket(message);
                    }
                }
            }
            catch (SocketException)
            {
                if (isRunning)
                    Debug.LogWarning("UDP socket exception while receiving.");
            }
            catch (Exception ex)
            {
                if (isRunning)
                    Debug.LogError("UDP receive error: " + ex.Message);
            }
        }
    }

    void ParsePacket(string message)
    {
        string[] parts = message.Split(',');

        if (parts.Length != 70)
        {
            if (logRawMessages)
                Debug.LogWarning($"Expected 70 values, got {parts.Length}. Raw: {message}");
            return;
        }

        for (int i = 0; i < 70; i++)
        {
            string s = parts[i].Trim();

            if (string.Equals(s, "NaN", StringComparison.OrdinalIgnoreCase))
            {
                latestValues[i] = float.NaN;
            }
            else if (!float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out latestValues[i]))
            {
                latestValues[i] = float.NaN;
            }
        }

        alphaAverage = AverageRange(16, 23);
        betaAverage = AverageRange(24, 47);
        gammaAverage = AverageRange(48, 55);

        if (logRawMessages)
            Debug.Log($"Alpha={alphaAverage:F4}, Beta={betaAverage:F4}, Gamma={gammaAverage:F4}");
    }

    float AverageRange(int startInclusive, int endInclusive)
    {
        float sum = 0f;
        int count = 0;

        for (int i = startInclusive; i <= endInclusive; i++)
        {
            if (!float.IsNaN(latestValues[i]))
            {
                sum += latestValues[i];
                count++;
            }
        }

        return count > 0 ? sum / count : 0f;
    }

    void OnApplicationQuit()
    {
        StopReceiver();
    }

    void OnDestroy()
    {
        StopReceiver();
    }

    void StopReceiver()
    {
        isRunning = false;

        try
        {
            socket?.Close();
        }
        catch { }

        try
        {
            if (receiveThread != null && receiveThread.IsAlive)
                receiveThread.Join(200);
        }
        catch { }
    }
}