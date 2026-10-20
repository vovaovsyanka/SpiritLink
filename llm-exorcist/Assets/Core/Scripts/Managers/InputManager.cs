using System;
using System.Linq;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.SceneManagement;


public class InputManager : MonoBehaviour
{
    public static InputManager Instance { get; private set; }
    public event EventHandler OnInteractAction;
    public event EventHandler OnPauseAction;
    public event EventHandler OnMenuSwitchUp;
    public event EventHandler OnMenuSwitchDown;
    public event EventHandler OnMenuButtonPressed;
    public event EventHandler OnSecretInputSolved;


    private static readonly string[] _mainMenuSecretInput = { "rulada",  "рулада", "hekflf", "кгдфвф" };

    private PlayerInputActions _playerInputActions;
    private MenuInputActions _menuInputActions;
    private string _mainMenuPlayerSecretInput;
    
    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            Destroy(gameObject);
        }
        
        _playerInputActions = new PlayerInputActions();
        _playerInputActions.Player.Enable();
        _playerInputActions.Player.Interact.performed += Interact_performed;
        _playerInputActions.Player.Pause.performed += Pause_performed;
        
        _menuInputActions = new MenuInputActions();
        _menuInputActions.Enable();
        _menuInputActions.Navigation.UpSwitch.performed += UpSwitch_performed;
        _menuInputActions.Navigation.DownSwitch.performed += DownSwitch_performed;
        _menuInputActions.Navigation.PressButton.performed += PressButton_performed;
    }

    private void Update()
    {
        if (SceneManager.GetActiveScene().name == SceneInfo.MAIN_MENU_SCENE 
            && !_mainMenuSecretInput.Contains(_mainMenuPlayerSecretInput)
            && GameStateManager.State != GameState.FirstEntry)
        {
            if (Input.anyKeyDown)
            {
                _mainMenuPlayerSecretInput += Input.inputString.ToLower();
                if (Input.inputString.ToLower() is "r" or "р" or "h" or "к")
                {
                    _mainMenuPlayerSecretInput = Input.inputString.ToLower();
                }

                if (_mainMenuPlayerSecretInput.Length > 7)
                {
                    _mainMenuPlayerSecretInput = "";
                }
            }
            
            if (_mainMenuSecretInput.Contains(_mainMenuPlayerSecretInput))
            {
                OnSecretInputSolved?.Invoke(this, EventArgs.Empty);
            }
        }
    }

    private void Pause_performed(InputAction.CallbackContext obj)
    {
        OnPauseAction?.Invoke(this, EventArgs.Empty);
    }

    private void PressButton_performed(InputAction.CallbackContext obj)
    {
        if (GameManager.IsGamePaused)
        {
            GameManager.TimeScaleZeroInvoke(this, EventArgs.Empty, OnMenuButtonPressed);
        }
        else
        {
            OnMenuButtonPressed?.Invoke(this, EventArgs.Empty);
        }
    }

    private void DownSwitch_performed(InputAction.CallbackContext obj)
    {
        if (GameManager.IsGamePaused)
        {
            GameManager.TimeScaleZeroInvoke(this, EventArgs.Empty, OnMenuSwitchDown);
        }
        else
        {
            OnMenuSwitchDown?.Invoke(this, EventArgs.Empty);
        }
    }

    private void UpSwitch_performed(InputAction.CallbackContext obj)
    {
        if (GameManager.IsGamePaused)
        {
            GameManager.TimeScaleZeroInvoke(this, EventArgs.Empty, OnMenuSwitchUp);
        }
        else
        {
            OnMenuSwitchUp?.Invoke(this, EventArgs.Empty);
        }
    }

    public Vector2 GetMovementVector()
    {
        Vector2 movementVector = _playerInputActions.Player.Move.ReadValue<Vector2>();
        float x = movementVector.x > 0 ? 1 : movementVector.x < 0 ? -1 : 0;
        float y = movementVector.y > 0 ? 1 : movementVector.y < 0 ? -1 : 0;
        return new Vector2(x, y);
    }
    
    private void Interact_performed(InputAction.CallbackContext obj)
    {
        OnInteractAction?.Invoke(this, EventArgs.Empty);
    }


    private void OnDisable()
    {
        _playerInputActions.Player.Interact.performed -= Interact_performed;
        _playerInputActions.Player.Disable();

        _menuInputActions.Navigation.UpSwitch.performed -= UpSwitch_performed;
        _menuInputActions.Navigation.DownSwitch.performed -= DownSwitch_performed;
        _menuInputActions.Navigation.PressButton.performed -= PressButton_performed;
        _menuInputActions.Disable();
    }
}
