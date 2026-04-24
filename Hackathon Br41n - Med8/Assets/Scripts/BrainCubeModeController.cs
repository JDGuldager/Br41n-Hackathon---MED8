using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

public class BrainCubeModeController : MonoBehaviour
{
    public enum BrainMode
    {
        MoveLeftRight,
        ScaleY
    }

    [Header("UDP")]
    public int port = 12346;

    [Header("Mode")]
    public BrainMode currentMode = BrainMode.MoveLeftRight;

    [Header("Movement")]
    public float moveSpeed = 3f;
    public float moveSmoothSpeed = 6f;

    [Header("Y Scaling")]
    public float minY = 1f;
    public float maxY = 5f;
    public float scaleIncreaseSpeed = 2f;
    public float scaleDecaySpeed = 1f;

    private Socket socket;
    private Thread thread;
    private volatile bool running = false;

    private readonly object dataLock = new object();

    private float targetDirection = 0f;
    private float smoothedDirection = 0f;

    private float currentYScale = 1f;

    void Start()
    {
        currentYScale = transform.localScale.y;

        socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
        socket.Bind(new IPEndPoint(IPAddress.Any, port));

        running = true;
        thread = new Thread(ReceiveLoop);
        thread.IsBackground = true;
        thread.Start();

        Debug.Log("BrainCube listening on UDP port " + port);
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

                lock (dataLock)
                {
                    HandleMessage(msg);
                }
            }
            catch
            {
                // Ignore shutdown errors
            }
        }
    }

    void HandleMessage(string msg)
    {
        Debug.Log("Received UDP: " + msg);
        if (msg == "TOGGLE")
        {
            ToggleMode();
            return;
        }

        if (msg.StartsWith("MOVE:"))
        {
            string value = msg.Substring(5);

            if (float.TryParse(value, out float dir))
                targetDirection = Mathf.Clamp(dir, -1f, 1f);
        }
    }

    void ToggleMode()
    {
        if (currentMode == BrainMode.MoveLeftRight)
        {
            currentMode = BrainMode.ScaleY;
            targetDirection = 0f;
            Debug.Log("Mode switched to: Scale Y");
        }
        else
        {
            currentMode = BrainMode.MoveLeftRight;
            Debug.Log("Mode switched to: Move Left/Right");
        }
    }

    void Update()
    {
        if (currentMode == BrainMode.MoveLeftRight)
        {
            UpdateMovementMode();
        }
        else
        {
            UpdateScaleMode();
        }
    }

    void UpdateMovementMode()
    {
        smoothedDirection = Mathf.Lerp(
            smoothedDirection,
            targetDirection,
            Time.deltaTime * moveSmoothSpeed
        );

        transform.position += Vector3.right * smoothedDirection * moveSpeed * Time.deltaTime;

        // Slowly return scale to normal while moving
        currentYScale = Mathf.Lerp(currentYScale, 1f, Time.deltaTime * scaleDecaySpeed);
        transform.localScale = new Vector3(1f, currentYScale, 1f);
    }

    void UpdateScaleMode()
    {
        // Stop horizontal movement
        smoothedDirection = Mathf.Lerp(smoothedDirection, 0f, Time.deltaTime * moveSmoothSpeed);

        // While in scale mode, increase Y size
        currentYScale += scaleIncreaseSpeed * Time.deltaTime;
        currentYScale = Mathf.Clamp(currentYScale, minY, maxY);

        transform.localScale = new Vector3(1f, currentYScale, 1f);
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

    void OnApplicationQuit()
    {
        running = false;

        try { socket?.Close(); } catch { }
    }
}