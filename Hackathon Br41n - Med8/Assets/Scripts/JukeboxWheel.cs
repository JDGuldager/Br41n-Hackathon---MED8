using UnityEngine;
using UnityEngine.InputSystem;

public class JukeboxWheel : MonoBehaviour
{
    [Header("CD Setup")]
    public float radius = 3f;
    public float cdHeight = 0f;
    public float selectedHeightOffset = 0.5f;

    [Header("Selection Manager")]
    public CDSelectionManager selectionManager;

    [Header("Transparency")]
    public float selectedAlpha = 1f;
    public float unselectedAlpha = 0.4f;

    [Header("Selected CD Effects")]
    public float selectedScale = 1.15f;
    public float selectedForwardPush = 0.25f;
    public float effectSmoothTime = 0.12f;

    [Header("CD Facing")]
    public float cdYRotationOffset = 90f;

    [Header("Selection")]
    public float selectionAngleOffset = -30f;

    [Header("Rotation")]
    public float rotationSmoothTime = 0.18f;

    private Transform[] cds;
    private Vector3[] basePositions;
    private Vector3[] baseScales;
    private Vector3[] positionVelocities;
    private Vector3[] scaleVelocities;

    private Renderer[][] renderers;
    private float[] alphaVelocities;

    private float targetYRotation;
    private float rotationVelocity;

    private int selectedIndex = 0;
    private int previousSelectedIndex = -1;

    void Awake()
    {
        CollectChildren();
        ArrangeCDs();

        if (selectionManager != null)
        {
            selectionManager.RegisterCDs(cds);
        }

        targetYRotation = transform.eulerAngles.y;

        if (selectionManager != null && cds.Length > 0)
        {
            selectionManager.SetHoveredCD(cds[selectedIndex]);
        }
    }

    void Update()
    {
        if (cds == null || cds.Length == 0) return;

        float smoothedY = Mathf.SmoothDampAngle(
            transform.eulerAngles.y,
            targetYRotation,
            ref rotationVelocity,
            rotationSmoothTime
        );

        transform.rotation = Quaternion.Euler(0f, smoothedY, 0f);

        HandleInput();
        UpdateSelectedCD();
        AnimateCDs();
        AnimateTransparency();
    }

    public void RotateLeft()
    {
        if (cds == null || cds.Length == 0) return;
        targetYRotation += 360f / cds.Length;
    }

    public void RotateRight()
    {
        if (cds == null || cds.Length == 0) return;
        targetYRotation -= 360f / cds.Length;
    }

    public void SelectCurrentCD()
    {
        if (selectionManager == null) return;

        Transform cd = GetSelectedCD();
        selectionManager.ToggleCD(cd);
    }

    public Transform GetSelectedCD()
    {
        if (cds == null || cds.Length == 0) return null;
        return cds[selectedIndex];
    }

    private void CollectChildren()
    {
        int count = transform.childCount;

        cds = new Transform[count];
        basePositions = new Vector3[count];
        baseScales = new Vector3[count];
        positionVelocities = new Vector3[count];
        scaleVelocities = new Vector3[count];

        renderers = new Renderer[count][];
        alphaVelocities = new float[count];

        for (int i = 0; i < count; i++)
        {
            cds[i] = transform.GetChild(i);
            baseScales[i] = cds[i].localScale;
            renderers[i] = cds[i].GetComponentsInChildren<Renderer>();
        }
    }

    private void ArrangeCDs()
    {
        if (cds == null || cds.Length == 0) return;

        float angleStep = 360f / cds.Length;

        for (int i = 0; i < cds.Length; i++)
        {
            float angleDeg = i * angleStep;
            float angleRad = angleDeg * Mathf.Deg2Rad;

            Vector3 localPos = new Vector3(
                Mathf.Sin(angleRad) * radius,
                cdHeight,
                Mathf.Cos(angleRad) * radius
            );

            cds[i].localPosition = localPos;
            basePositions[i] = localPos;

            cds[i].localRotation = Quaternion.Euler(
                0f,
                angleDeg + cdYRotationOffset,
                0f
            );
        }
    }

    private void UpdateSelectedCD()
    {
        float angleStep = 360f / cds.Length;
        float wheelY = transform.eulerAngles.y;

        float targetAngle = -wheelY + selectionAngleOffset;
        int closestIndex = Mathf.RoundToInt(targetAngle / angleStep);

        selectedIndex = Mod(closestIndex, cds.Length);

        if (selectedIndex != previousSelectedIndex)
        {
            previousSelectedIndex = selectedIndex;

            if (selectionManager != null)
            {
                selectionManager.SetHoveredCD(cds[selectedIndex]);
            }
        }
    }

    private void AnimateCDs()
    {
        for (int i = 0; i < cds.Length; i++)
        {
            Vector3 targetPos = basePositions[i];
            Vector3 targetScale = baseScales[i];

            if (i == selectedIndex)
            {
                targetPos.y = cdHeight + selectedHeightOffset;

                if (Camera.main != null)
                {
                    Vector3 pushDirection =
                        transform.InverseTransformDirection(Camera.main.transform.forward);

                    targetPos += pushDirection.normalized * selectedForwardPush;
                }

                targetScale = baseScales[i] * selectedScale;
            }

            cds[i].localPosition = Vector3.SmoothDamp(
                cds[i].localPosition,
                targetPos,
                ref positionVelocities[i],
                effectSmoothTime
            );

            cds[i].localScale = Vector3.SmoothDamp(
                cds[i].localScale,
                targetScale,
                ref scaleVelocities[i],
                effectSmoothTime
            );
        }
    }

    private void AnimateTransparency()
    {
        for (int i = 0; i < cds.Length; i++)
        {
            bool isFocused = i == selectedIndex;
            bool isChosen = selectionManager != null && selectionManager.IsSelected(cds[i]);

            float targetAlpha = (isFocused || isChosen)
                ? selectedAlpha
                : unselectedAlpha;

            foreach (Renderer rend in renderers[i])
            {
                if (rend == null) continue;

                foreach (Material mat in rend.materials)
                {
                    Color color = mat.color;

                    color.a = Mathf.SmoothDamp(
                        color.a,
                        targetAlpha,
                        ref alphaVelocities[i],
                        effectSmoothTime
                    );

                    mat.color = color;
                }
            }
        }
    }

    private int Mod(int value, int length)
    {
        return ((value % length) + length) % length;
    }

    void OnValidate()
    {
        if (!Application.isPlaying)
        {
            CollectChildren();
            ArrangeCDs();
        }
    }
    private void HandleInput()
    {
        if (Keyboard.current == null) return;

        if (Keyboard.current.leftArrowKey.wasPressedThisFrame)
        {
            RotateLeft();
        }

        if (Keyboard.current.rightArrowKey.wasPressedThisFrame)
        {
            RotateRight();
        }

        if (Keyboard.current.upArrowKey.wasPressedThisFrame)
        {
            SelectCurrentCD();
        }
    }
}