using UnityEngine;

public class InstantChatEnder : AbstractChatEnder
{
    [SerializeField] private GameState _nextGameState;

    [ContextMenu("EndLevel")]
    protected override void EndChatMethod()
    {
        GameStateManager.State = _nextGameState;
        GameManager.Instance.LoadMapScene();
    }
}
