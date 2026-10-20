using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.Events;


public class ButtonContainer : MonoBehaviour
{
    [SerializeField] public List<TextMeshProUGUI> Buttons;
    [SerializeField] private Color _selectedColorText = Color.black;
    [SerializeField] private Color _unselectedColorText = new (0.490566f, 0.490566f, 0.490566f, 1f);
    public static event EventHandler OnButtonPressed;
    protected bool _isSubscribed;
    protected bool _wasSubscribedInStart;
    
    protected int SelectedButtonId;

    private void Start()
    {
        if (!_isSubscribed)
        {
            Subscribe();
            InitializeContainer();
            _wasSubscribedInStart = true;
        }
    }

    private void MenuButton_OnPlayButtonPressed(object sender, EventArgs e)
    {
        if (_isSubscribed)
        {
            Unsubscribe();
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
    
    protected virtual void Subscribe()
    {
        _isSubscribed = true;
        
        InputManager.Instance.OnMenuSwitchUp += InputManager_OnMenuSwitchUp;
        InputManager.Instance.OnMenuSwitchDown += InputManager_OnMenuSwitchDown;
        InputManager.Instance.OnMenuButtonPressed += InputManager_OnMenuButtonPressed;
        MenuButton.OnPlayButtonPressed += MenuButton_OnPlayButtonPressed;
    }
    
    protected virtual void Unsubscribe()
    {
        _isSubscribed = false;
        
        InputManager.Instance.OnMenuSwitchUp -= InputManager_OnMenuSwitchUp;
        InputManager.Instance.OnMenuSwitchDown -= InputManager_OnMenuSwitchDown;
        InputManager.Instance.OnMenuButtonPressed -= InputManager_OnMenuButtonPressed;
        MenuButton.OnPlayButtonPressed -= MenuButton_OnPlayButtonPressed;

    }


    private void InputManager_OnMenuButtonPressed(object sender, EventArgs e)
    {
        if (!GameManager.IsGamePaused)
        {
            PressButton();
        }
    }

    private void InputManager_OnMenuSwitchUp(object sender, EventArgs e)
    {
        if (!GameManager.IsGamePaused)
        {
            SwitchButtonUp();
        }
    }

    private void InputManager_OnMenuSwitchDown(object sender, EventArgs e)
    {
        if (!GameManager.IsGamePaused)
        {
            SwitchButtonDown();
        }
    }

    protected void PressButton()
    {
        if (Buttons.Count == 0) return;
        UnityEvent unityEvent = Buttons[SelectedButtonId].gameObject.GetComponentInParent<MenuButton>().OnPressMethod;
        if (GameManager.IsGamePaused)
        {
            GameManager.TimeScaleZeroInvoke(unityEvent);
        }
        else
        {
            Buttons[SelectedButtonId].gameObject.GetComponentInParent<MenuButton>().OnPressMethod.Invoke();
        }
    }

    protected void SwitchButtonUp()
    {
        if (Buttons.Count == 0) return;
        if (SelectedButtonId-1 > Buttons.Count)
        {
            return;
        }
        if (SelectedButtonId > 0)
        {
            DeselectButton(SelectedButtonId);
            SelectedButtonId--;
            SelectButton(SelectedButtonId);
            OnButtonPressed?.Invoke(this, EventArgs.Empty);
        }
    }

    protected void SwitchButtonDown()
    {
        if (Buttons.Count == 0) return;
        if (SelectedButtonId < Buttons.Count - 1)
        {
            DeselectButton(SelectedButtonId);
            SelectedButtonId++;
            SelectButton(SelectedButtonId);
            OnButtonPressed?.Invoke(this, EventArgs.Empty);
        }
    }

    protected void SelectButton(int buttonId)
    {
        Buttons[buttonId].color = _selectedColorText;
        if (Buttons[buttonId].text.StartsWith(">"))
        {
            Buttons[buttonId].text = Buttons[buttonId].text.Substring(1, Buttons[buttonId].text.Length - 2);
        }
        Buttons[buttonId].text = ">" + Buttons[buttonId].text + "<";
    }

    protected void DeselectButton(int buttonId)
    {
        Buttons[buttonId].color = _unselectedColorText;
        if (Buttons[buttonId].text.StartsWith(">"))
        {
            Buttons[buttonId].text = Buttons[buttonId].text.Substring(1, Buttons[buttonId].text.Length - 2);
        }
    }

    public void AddButton(TextMeshProUGUI buttonText)
    {
        Buttons.Add(buttonText);
        if (Buttons.Count == 1)
        {
            SelectedButtonId = 0;
            SelectButton(0);
        }

        for (int i = 0; i < Buttons.Count; i++)
        {
            if (i != SelectedButtonId)
            {
                DeselectButton(i);
            }
        }
    }

    private void InitializeContainer()
    {
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

    public void SetButtonActive(GameObject menuButton, bool active)
    {
        menuButton.SetActive(active);
        if (!active)
        {
            Buttons.Remove(menuButton.GetComponentInChildren<TextMeshProUGUI>());
        }
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
