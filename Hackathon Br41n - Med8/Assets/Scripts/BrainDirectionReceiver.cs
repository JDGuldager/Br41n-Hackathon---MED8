using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

public class BrainDirectionReceiver : MonoBehaviour
{
    public int port = 12346;
    public float moveSpeed = 3f;
    public float smoothSpeed = 6f;

    private Socket socket;
    private Thread thread;
    private volatile bool running = false;

    private float targetDirection = 0f;
    private float smoothedDirection = 0f;

    void Start()
    {
        socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
        socket.Bind(new IPEndPoint(IPAddress.Any, port));

        running = true;
        thread = new Thread(ReceiveLoop);
        thread.IsBackground = true;
        thread.Start();

        Debug.Log("Listening for MI commands on UDP port " + port);
    }

    void ReceiveLoop()
    {
        byte[] buffer = new byte[256];

        while (running)
        {
            try
            {
                int count = socket.Receive(buffer);
                string msg = Encoding.ASCII.GetString(buffer, 0, count).Trim();

                if (float.TryParse(msg, out float dir))
                {
                    targetDirection = Mathf.Clamp(dir, -1f, 1f);
                }
            }
            catch
            {
                // Ignore socket shutdown errors.
            }
        }
    }

    void Update()
    {
        smoothedDirection = Mathf.Lerp(
            smoothedDirection,
            targetDirection,
            Time.deltaTime * smoothSpeed
        );

        transform.position += Vector3.right * smoothedDirection * moveSpeed * Time.deltaTime;
    }

    void OnDestroy()
    {
        running = false;

        try { socket?.Close(); } catch { }

        try
        {
            if (thread != null && thread.IsAlive)
                thread.Join(200);
        }
        catch { }
    }
}