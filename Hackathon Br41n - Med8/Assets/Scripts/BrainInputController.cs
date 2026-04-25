using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using UnityEngine.Events;

public class BrainInputController : MonoBehaviour
{
    public enum BrainDirection
    {
        None = 0,
        Left = -1,
        Right = 1
    }

    [Header("UDP")]
    public int port = 12346;

    [Header("Voting")]
    public float voteWindowSeconds = 2f;
    public bool ignoreIdleVotes = true;

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

    [Header("Debug")]
    public BrainDirection latestRawDirection = BrainDirection.None;
    public BrainDirection lastChosenDirection = BrainDirection.None;
    public int leftVotes = 0;
    public int rightVotes = 0;
    public int idleVotes = 0;

    [Header("Events")]
    public UnityEvent onLeftChosen;
    public UnityEvent onRightChosen;
    public UnityEvent onIdleChosen;
    public UnityEvent onToggle;

    private Socket socket;
    private Thread thread;
    private volatile bool running = false;

    private readonly object dataLock = new object();
    private readonly List<BrainDirection> voteBuffer = new List<BrainDirection>();

    private float voteTimer = 0f;

    void Start()
    {
        socket = new Socket(AddressFamily.InterNetwork, SocketType.Dgram, ProtocolType.Udp);
        socket.Bind(new IPEndPoint(IPAddress.Any, port));

        running = true;
        thread = new Thread(ReceiveLoop);
        thread.IsBackground = true;
        thread.Start();

        Debug.Log("BrainInputController listening on UDP port " + port);
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
        if (msg == "TOGGLE")
        {
            // UnityEvents should be invoked on main thread,
            // so we store the toggle as a special vote-like action.
            latestRawDirection = BrainDirection.None;
            voteBuffer.Add(BrainDirection.None);

            // Mark toggle by setting a flag through main-thread-safe call pattern
            toggleRequested = true;
            return;
        }

        string[] parts = msg.Split(';');

        foreach (string part in parts)
        {
            if (part.StartsWith("MOVE:"))
            {
                string value = part.Substring(5);

                if (float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out float dir))
                {
                    BrainDirection parsedDirection = BrainDirection.None;

                    if (dir < 0f)
                        parsedDirection = BrainDirection.Left;
                    else if (dir > 0f)
                        parsedDirection = BrainDirection.Right;

                    latestRawDirection = parsedDirection;
                    voteBuffer.Add(parsedDirection);
                }
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

    private bool toggleRequested = false;

    void Update()
    {
        SmoothBrainValues();

        if (toggleRequested)
        {
            toggleRequested = false;
            onToggle?.Invoke();
            Debug.Log("Brain toggle event fired.");
        }

        voteTimer += Time.deltaTime;

        if (voteTimer >= voteWindowSeconds)
        {
            voteTimer = 0f;
            ChooseMajorityDirection();
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

    void ChooseMajorityDirection()
    {
        List<BrainDirection> votesCopy;

        lock (dataLock)
        {
            votesCopy = new List<BrainDirection>(voteBuffer);
            voteBuffer.Clear();
        }

        leftVotes = 0;
        rightVotes = 0;
        idleVotes = 0;

        foreach (BrainDirection vote in votesCopy)
        {
            if (vote == BrainDirection.Left)
                leftVotes++;
            else if (vote == BrainDirection.Right)
                rightVotes++;
            else
                idleVotes++;
        }

        BrainDirection chosen = BrainDirection.None;

        if (leftVotes > rightVotes)
        {
            chosen = BrainDirection.Left;
        }
        else if (rightVotes > leftVotes)
        {
            chosen = BrainDirection.Right;
        }
        else if (!ignoreIdleVotes && idleVotes > leftVotes && idleVotes > rightVotes)
        {
            chosen = BrainDirection.None;
        }
        else
        {
            chosen = BrainDirection.None;
        }

        lastChosenDirection = chosen;

        if (chosen == BrainDirection.Left)
        {
            Debug.Log($"Majority vote: LEFT | L={leftVotes}, R={rightVotes}, Idle={idleVotes}");
            onLeftChosen?.Invoke();
        }
        else if (chosen == BrainDirection.Right)
        {
            Debug.Log($"Majority vote: RIGHT | L={leftVotes}, R={rightVotes}, Idle={idleVotes}");
            onRightChosen?.Invoke();
        }
        else
        {
            Debug.Log($"Majority vote: IDLE/TIE | L={leftVotes}, R={rightVotes}, Idle={idleVotes}");
            onIdleChosen?.Invoke();
        }
    }

    void OnDestroy()
    {
        StopReceiver();
    }

    void OnApplicationQuit()
    {
        StopReceiver();
    }

    void StopReceiver()
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