
using UnityEngine;
using UnityEngine.UIElements;
using static UnityEngine.GraphicsBuffer;


public class PlayerMovement : MonoBehaviour
{
    public Transform[] positions; // 0 = left, 1 = mid, 2 = right

    private int currentIndex = 1; // start at mid
    private bool isMoving = false;
    private Vector3 target;

    private float speed = 2f;

    [SerializeField] private Animator playerAnimator;

    private bool isRotatingToFinal = false;
    private Quaternion finalRotation = Quaternion.Euler(0f, -90f, 0f);

    // Start is called once before the first execution of Update after the MonoBehaviour is created
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        if (isMoving)
        {
            Vector3 direction = (target - transform.position);
            direction.y = 0f;

            if (direction != Vector3.zero)
            {
                Quaternion targetRotation = Quaternion.LookRotation(direction);
                transform.rotation = Quaternion.Slerp(
                    transform.rotation,
                    targetRotation,
                    10f * Time.deltaTime
                );
            }

            transform.position = Vector3.MoveTowards(
                transform.position,
                target,
                speed * Time.deltaTime                
            );

            // Stop when close enough
            if (Vector3.Distance(transform.position, target) < 0.01f)
            {
                playerAnimator.SetBool("isMoving", false);
                isMoving = false;

                
                isRotatingToFinal = true;
            }
        }

        if (isRotatingToFinal)
        {
            transform.rotation = Quaternion.Slerp(
                transform.rotation,
                finalRotation,
                5f * Time.deltaTime
            );

            if (Quaternion.Angle(transform.rotation, finalRotation) < 0.5f)
            {
                transform.rotation = finalRotation;
                isRotatingToFinal = false;
            }
        }
    }

    public void WalkTo(bool moveRight)
    {
        if (isMoving)
        {
            Debug.Log("Already moving");
            return;
        }

        int direction = moveRight ? 1 : -1;
        int newIndex = currentIndex + direction;

        // Clamp to valid range
        if (newIndex < 0 || newIndex >= positions.Length)
        {
            Debug.Log("Can't walk further " + (moveRight ? "right" : "left"));
            return;
        }

        currentIndex = newIndex;
        target = positions[currentIndex].position;
        playerAnimator.SetBool("isMoving", true);
        isMoving = true;
        
    }


}
