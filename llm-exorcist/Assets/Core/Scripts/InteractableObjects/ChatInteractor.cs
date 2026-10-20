using UnityEngine;
using UnityEngine.InputSystem;

namespace Assets.Core.Scripts.Chat
{
    public class ChatInteractor : InteractableObject
    {
        public static bool IsChatOpen { get; private set; }

        [SerializeField] private MessageSpawner _messageSpawner;

        private InputSystem_Actions _inputSystem_Actions;

        private void OnEnable()
        {
            _messageSpawner.gameObject.SetActive(false);
            IsChatOpen = false;

            _inputSystem_Actions = new();
            _inputSystem_Actions.Enable();

            _inputSystem_Actions.Chat.ToogleChat.performed += ToogleChat;
        }

        private void OnDisable()
        {
            _inputSystem_Actions.Chat.ToogleChat.performed -= ToogleChat;

            _inputSystem_Actions.Disable();
        }

        public override void Interact()
        {
            return;
        }

        private void ToogleChat(InputAction.CallbackContext obj)
        {
            if (!_messageSpawner.IsRequestInProgress)
            {
                _messageSpawner.gameObject.SetActive(!_messageSpawner.gameObject.activeSelf);
                IsChatOpen = _messageSpawner.gameObject.activeSelf;
            }
        }
    }
}
