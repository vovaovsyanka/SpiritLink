using UnityEngine;

public abstract class AbstractChatEnder : MonoBehaviour
{
    protected void OnEnable()
    {
        MessageSpawner.OnChatEnded += EndChatMethod;
    }

    protected void OnDisable()
    {
        MessageSpawner.OnChatEnded -= EndChatMethod;
    }

    protected abstract void EndChatMethod();
}
