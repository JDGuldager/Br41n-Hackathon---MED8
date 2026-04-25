using System;
using System.Globalization;
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

    [Header("Brain Values")]
    public float brainConfidence = 0f;
    public float alphaAverage = 0f;
    public float betaAverage = 0f;
    public float gammaAverage = 0f;

    [Header("Smoothed Brain Values")]
    public float smoothedConfidence = 0f;
    public float smoothedAlpha = 0f;
    public float smoothedBeta = 0f;
    public float smoothedGamma = 0f;
    public float brainValueSmoothSpeed = 5f;

    [Header("Movement")]
    public float moveSpeed = 3f;
    public float moveSmoothSpeed = 6f;

    [Header("Movement Limits")]
    public float minX = -5f;
    public float maxX = 5f;

    [Header("Y Scaling")]
    public float minY = 1f;
    public float maxY = 5f;
    public float scaleIncreaseSpeed = 2f;
    public float scaleDecaySpeed = 1f;

    [Header("Scale Mode Signal")]
    public bool scaleWithConfidence = true;
    public bool scaleWithAlpha = false;
    public bool scaleWithBeta = false;
    public bool scaleWithGamma = false;
    public float scaleSignalMultiplier = 1f;

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
        byte[] buffer = new byte[512];

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

        string[] parts = msg.Split(';');

        foreach (string part in parts)
        {
            if (part.StartsWith("MOVE:"))
            {
                string value = part.Substring(5);

                if (float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out float dir))
                    targetDirection = Mathf.Clamp(dir, -1f, 1f);
            }
            else if (part.StartsWith("CONF:"))
            {
                string value = part.Substring(5);

                if (float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out float conf))
                    brainConfidence = Mathf.Clamp01(conf);
            }
            else if (part.StartsWith("ALPHA:"))
            {
                string value = part.Substring(6);

                if (float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out float alpha))
                    alphaAverage = alpha;
            }
            else if (part.StartsWith("BETA:"))
            {
                string value = part.Substring(5);

                if (float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out float beta))
                    betaAverage = beta;
            }
            else if (part.StartsWith("GAMMA:"))
            {
                string value = part.Substring(6);

                if (float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out float gamma))
                    gammaAverage = gamma;
            }
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
        SmoothBrainValues();

        if (currentMode == BrainMode.MoveLeftRight)
        {
            UpdateMovementMode();
        }
        else
        {
            UpdateScaleMode();
        }
    }

    void SmoothBrainValues()
    {
        smoothedConfidence = Mathf.Lerp(
            smoothedConfidence,
            brainConfidence,
            Time.deltaTime * brainValueSmoothSpeed
        );

        smoothedAlpha = Mathf.Lerp(
            smoothedAlpha,
            alphaAverage,
            Time.deltaTime * brainValueSmoothSpeed
        );

        smoothedBeta = Mathf.Lerp(
            smoothedBeta,
            betaAverage,
            Time.deltaTime * brainValueSmoothSpeed
        );

        smoothedGamma = Mathf.Lerp(
            smoothedGamma,
            gammaAverage,
            Time.deltaTime * brainValueSmoothSpeed
        );
    }

    void UpdateMovementMode()
    {
        smoothedDirection = Mathf.Lerp(
            smoothedDirection,
            targetDirection,
            Time.deltaTime * moveSmoothSpeed
        );

        Vector3 pos = transform.position;
        pos.x += smoothedDirection * moveSpeed * Time.deltaTime;
        pos.x = Mathf.Clamp(pos.x, minX, maxX);
        transform.position = pos;

        currentYScale = Mathf.Lerp(currentYScale, 1f, Time.deltaTime * scaleDecaySpeed);
        transform.localScale = new Vector3(1f, currentYScale, 1f);
    }

    void UpdateScaleMode()
    {
        smoothedDirection = Mathf.Lerp(smoothedDirection, 0f, Time.deltaTime * moveSmoothSpeed);

        float signal = GetSelectedScaleSignal();
        float boost = Mathf.Max(0f, signal * scaleSignalMultiplier);

        currentYScale += scaleIncreaseSpeed * boost * Time.deltaTime;
        currentYScale = Mathf.Clamp(currentYScale, minY, maxY);

        transform.localScale = new Vector3(1f, currentYScale, 1f);
    }

    float GetSelectedScaleSignal()
    {
        if (scaleWithAlpha)
            return smoothedAlpha;

        if (scaleWithBeta)
            return smoothedBeta;

        if (scaleWithGamma)
            return smoothedGamma;

        if (scaleWithConfidence)
            return smoothedConfidence;

        return smoothedConfidence;
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