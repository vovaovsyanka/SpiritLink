using System;
using UnityEngine;
using UnityEngine.UI;

public class MapManager : MonoBehaviour
{
    public class OnMapButtonClickEventArgs : EventArgs
    {
        public string SceneToLoadName;
    }

    public static event EventHandler<OnMapButtonClickEventArgs> OnMapButtonClick;

    [field: SerializeField] private Button _lvl1Buton;
    [SerializeField] private Button _lvl2Buton;
    [SerializeField] private Button _lvl3Buton;

    private void OnEnable()
    {
        _lvl1Buton.onClick.AddListener(() => Interact(SceneNames.lvl1));
        _lvl2Buton.onClick.AddListener(() => Interact(SceneNames.lvl2));
        _lvl3Buton.onClick.AddListener(() => Interact(SceneNames.lvl3));
    }

    private void OnDisable()
    {
        _lvl1Buton.onClick.RemoveAllListeners();
        _lvl2Buton.onClick.RemoveAllListeners();
        _lvl3Buton.onClick.RemoveAllListeners();
    }

    private void Start()
    {
        if(GameStateManager.State == GameState.map || GameStateManager.State == GameState.lvl1)
        {
            _lvl1Buton.interactable = true;
            _lvl2Buton.interactable = false;
            _lvl3Buton.interactable = false;
        }
        if (GameStateManager.State == GameState.lvl2)
        {
            _lvl1Buton.interactable = true;
            _lvl2Buton.interactable = true;
            _lvl3Buton.interactable = false;
        }
        if (GameStateManager.State == GameState.lvl3)
        {
            _lvl1Buton.interactable = true;
            _lvl2Buton.interactable = true;
            _lvl3Buton.interactable = true;
        }
    }

    private void Interact(SceneNames sceneName)
    {
        OnMapButtonClick?.Invoke(this, new OnMapButtonClickEventArgs
        {
            SceneToLoadName = SceneInfo.SceneNamesMap[sceneName]
        });
    }
}
