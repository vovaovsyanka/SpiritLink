using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

public class PauseButtonContainer : ButtonContainer
{
    [SerializeField] private List<TextMeshProUGUI> _defaultButtons;
    [SerializeField] private GameObject _defaultButtonsGroup;
    [SerializeField] private List<TextMeshProUGUI> _hiddenButtons;
    [SerializeField] private GameObject _hiddenButtonsGroup;

    
    private void Start()
    {
        _defaultButtonsGroup.SetActive(true);
        _hiddenButtonsGroup.SetActive(false);
        if (!_isSubscribed)
        {
            Subscribe();
            InitializeContainer();
            _wasSubscribedInStart = true;
        }
    }

    private void OnEnable()
    {
        if (_wasSubscribedInStart)
        {
            try
            {
                Subscribe();
                InitializeContainer();
            }
            catch (NullReferenceException e)
            {
                Console.WriteLine("mama " + e.Message);
            }
        }
    }
    
    private void InputManager_OnMenuSwitchUp(object sender, EventArgs e)
    {
        if (GameManager.IsGamePaused)
        {
            SwitchButtonUp();
        }
    }
    
    private void InputManager_OnMenuSwitchDown(object sender, EventArgs e)
    {
        if (GameManager.IsGamePaused)
        {
            SwitchButtonDown();
        }
    }
    
    private void InputManager_OnMenuButtonPressed(object sender, EventArgs e)
    {
        if (GameManager.IsGamePaused)
        {
            PressButton();
        }
    }


    private void MenuButton_OnHiddenButtonsNeedToSetActive(object sender, EventArgs e)
    {
        ResetActiveButtonsGroup();
    }
    
    private void InitializeContainer()
    {
        Buttons = _defaultButtons;
        SelectedButtonId = 0;
        
        for (int i = 0; i < Buttons.Count; i++)
        {
            DeselectButton(i);
        }
        if (Buttons.Count > 0)
        {
            SelectButton(SelectedButtonId);
        }
    }
    
    private void ResetActiveButtonsGroup()
    {
        for (int i = 0; i < Buttons.Count; i++)
        {
            DeselectButton(i);
        }
        
        if (_defaultButtonsGroup.activeSelf)
        {
            _defaultButtonsGroup.SetActive(false);
            _hiddenButtonsGroup.SetActive(true);
            Buttons = _hiddenButtons;
            SelectedButtonId = 0;
            SelectButton(SelectedButtonId);
        }
        else
        {
            _defaultButtonsGroup.SetActive(true);
            _hiddenButtonsGroup.SetActive(false);
            Buttons = _defaultButtons;
            SelectedButtonId = 0;
            SelectButton(SelectedButtonId);
        }
    }

    protected override void Subscribe()
    {
        base.Subscribe();
        InputManager.Instance.OnMenuSwitchUp += InputManager_OnMenuSwitchUp;
        InputManager.Instance.OnMenuSwitchDown += InputManager_OnMenuSwitchDown;
        InputManager.Instance.OnMenuButtonPressed += InputManager_OnMenuButtonPressed;
        MenuButton.OnHiddenButtonsNeedToSetActive += MenuButton_OnHiddenButtonsNeedToSetActive;
    }

    protected override void Unsubscribe()
    {
        base.Unsubscribe();
        InputManager.Instance.OnMenuSwitchUp -= InputManager_OnMenuSwitchUp;
        InputManager.Instance.OnMenuSwitchDown -= InputManager_OnMenuSwitchDown;
        InputManager.Instance.OnMenuButtonPressed -= InputManager_OnMenuButtonPressed;
        MenuButton.OnHiddenButtonsNeedToSetActive -= MenuButton_OnHiddenButtonsNeedToSetActive;
    }
    
    private void OnDestroy()
    {
        if (_isSubscribed)
        {
            Unsubscribe();
        }
    }
    
    private void OnDisable()
    {
        if (_isSubscribed)
        {
            Unsubscribe();
        }
    }
}
