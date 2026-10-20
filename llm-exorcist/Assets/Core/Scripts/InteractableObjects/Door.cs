using System;
using UnityEngine;


public class Door : InteractableObject
{
    [SerializeField] private bool _isAlwaysOpen = false;
    [SerializeField] private GameState _stateToOpen;
    [SerializeField] private SceneNames _sceneToLoad;
    
    public static event EventHandler<OnDoorOpenEventArgs> OnDoorOpen;
    public class OnDoorOpenEventArgs : EventArgs
    {
        public string SceneToLoadName;
        public Vector2 DoorPosition;
    }

    private void Start()
    {
        if (GameStateManager.State != _stateToOpen && !_isAlwaysOpen)
        {
            _isInteractable = false;
        }
        
        GameStateManager.OnStateChanged += GameStateManager_OnStateChanged;
    }

    private void GameStateManager_OnStateChanged(object sender, GameStateManager.OnStateChangedEventArgs e)
    {
        if (e.CurrentState == _stateToOpen)
        {
            _isInteractable = true;
        }
    }

    public override void Interact()
    {
        OnDoorOpen?.Invoke(this, new OnDoorOpenEventArgs {
            SceneToLoadName = SceneInfo.SceneNamesMap[_sceneToLoad], DoorPosition = transform.position
        });
    }

    private void OnDisable()
    {
        GameStateManager.OnStateChanged -= GameStateManager_OnStateChanged;
    }
}
