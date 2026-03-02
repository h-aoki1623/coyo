import { buildAudioFormData } from './useAudioRecording';

describe('buildAudioFormData', () => {
  it('creates a FormData with an audio field', () => {
    const formData = buildAudioFormData('file:///path/to/audio.m4a');

    // FormData.append should have been called
    expect(formData).toBeInstanceOf(FormData);
  });

  it('appends the audio field with correct structure', () => {
    const appendSpy = jest.spyOn(FormData.prototype, 'append');

    buildAudioFormData('file:///recordings/test.m4a');

    expect(appendSpy).toHaveBeenCalledWith('audio', expect.objectContaining({
      uri: 'file:///recordings/test.m4a',
      type: 'audio/mp4',
    }));

    appendSpy.mockRestore();
  });

  it('sets the file name with correct extension', () => {
    const appendSpy = jest.spyOn(FormData.prototype, 'append');

    buildAudioFormData('file:///test.m4a');

    const appendedValue = appendSpy.mock.calls[0][1] as unknown as {
      name: string;
    };
    expect(appendedValue.name).toMatch(/audio\.m4a$/);

    appendSpy.mockRestore();
  });

  it('handles different URI formats', () => {
    // Should not throw for any valid URI string
    expect(() => buildAudioFormData('file:///a.m4a')).not.toThrow();
    expect(() =>
      buildAudioFormData('file:///long/path/to/recording.m4a'),
    ).not.toThrow();
  });
});
