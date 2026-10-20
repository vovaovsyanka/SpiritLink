using UnityEngine;


public class PlayerSounds : MonoBehaviour
{
    private const float FOOTSTEPS_TIMER_MAX = .3f;
    private float _footstepsTimer;
    
    private void Update()
    {
        if (Player.Instance.IsMoving)
        {
            _footstepsTimer += Time.deltaTime;
            if (_footstepsTimer >= FOOTSTEPS_TIMER_MAX)
            {
                SoundManager.Instance.PlayFootstepsSound();
                _footstepsTimer = 0f;
            }
        }
        
    }
}
